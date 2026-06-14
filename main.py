import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput
from kivy.utils import platform
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.anchorlayout import AnchorLayout

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

class CameraRenamerApp(App):
    def build(self):
        self.file_names = ['Product_Front', 'Product_Back', 'Serial_Number', 'Receipt_Copy', 'Damage_Detail']
        self.completed_photos = set()
        self.photo_uris = {} 
        self.editing_index = -1
        self.press_hold_event = None
        self.folder_name = ""

        self.root_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        self.show_folder_setup_view()
        
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.CAMERA, Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])
            except Exception as e:
                print(f"Permission request failed: {e}")
            
        return self.root_layout

    def show_folder_setup_view(self):
        self.root_layout.clear_widgets()
        center_anchor = AnchorLayout(anchor_x='center', anchor_y='center')
        
        folder_layout = BoxLayout(orientation='vertical', spacing=15, size_hint=(0.85, None))
        folder_layout.bind(minimum_height=folder_layout.setter('height'))
        
        label = Label(text="Enter Session / Folder Name:", font_size='18sp', size_hint_y=None, height=40)
        self.folder_input = TextInput(hint_text="e.g., Inspection_101", multiline=False, size_hint_y=None, height=50)
        submit_btn = Button(text="Set Folder & Continue", size_hint_y=None, height=50, background_color=(0.1, 0.7, 0.3, 1))
        submit_btn.bind(on_press=self.submit_folder_name)
        
        folder_layout.add_widget(label)
        folder_layout.add_widget(self.folder_input)
        folder_layout.add_widget(submit_btn)
        
        center_anchor.add_widget(folder_layout)
        self.root_layout.add_widget(center_anchor)

    def submit_folder_name(self, instance):
        text = self.folder_input.text.strip().replace(" ", "_")
        if text:
            self.folder_name = text
            self.setup_main_list_view()
        else:
            self.folder_input.hint_text = "Name cannot be empty!"

    def setup_main_list_view(self):
        self.root_layout.clear_widgets()
        
        self.status_label = Label(
            text=f"Folder: {self.folder_name}\nTap to view/capture | Long-press to edit name", 
            size_hint_y=None, height=60, font_size='15sp', halign='center'
        )
        self.root_layout.add_widget(self.status_label)
        
        input_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=5)
        self.new_name_input = TextInput(hint_text="Type custom file name...", multiline=False)
        add_btn = Button(text="Add Name", size_hint_x=0.25)
        add_btn.bind(on_press=self.add_custom_name)
        input_layout.add_widget(self.new_name_input)
        input_layout.add_widget(add_btn)
        self.root_layout.add_widget(input_layout)

        scroll_view = ScrollView()
        self.grid_layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        self.grid_layout.bind(minimum_height=self.grid_layout.setter('height'))
        
        scroll_view.add_widget(self.grid_layout)
        self.root_layout.add_widget(scroll_view)
        
        self.save_pdf_btn = Button(
            text="Generate PDF Report (0 Photos)", 
            size_hint_y=None, 
            height=60, 
            background_color=(0.7, 0.7, 0.7, 1)
        )
        self.save_pdf_btn.bind(on_press=self.generate_pdf_report)
        self.root_layout.add_widget(self.save_pdf_btn)
        
        self.refresh_buttons()

    def refresh_buttons(self):
        self.grid_layout.clear_widgets()
        
        if hasattr(self, 'save_pdf_btn'):
            count = len(self.completed_photos)
            self.save_pdf_btn.text = f"Save & Generate PDF ({count} Photos)"
            if count > 0:
                self.save_pdf_btn.background_color = (0.1, 0.8, 0.4, 1)  
            else:
                self.save_pdf_btn.background_color = (0.7, 0.7, 0.7, 1)  

        for index, name in enumerate(self.file_names):
            row_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=65, spacing=5)
            
            if name in self.completed_photos:
                btn_color = (0.1, 0.7, 0.3, 1)  
                display_text = f"{name} ✓"
            else:
                btn_color = (0.1, 0.5, 0.9, 1)  
                display_text = name

            if self.editing_index == index:
                name_widget = TextInput(text=name, multiline=False, size_hint_x=0.85, focus=True)
                name_widget.bind(on_text_validate=lambda instance, idx=index: self.save_edited_name(idx, instance.text))
                name_widget.bind(focus=lambda instance, value, idx=index: Clock.schedule_once(lambda dt: self.check_focus_lost(instance, value, idx), 0.1))
                Window.show_keyboard()
            else:
                name_widget = Button(text=display_text, size_hint_x=0.85, background_color=btn_color)
                name_widget.bind(on_touch_down=lambda instance, touch, idx=index: self.on_press_down(instance, touch, idx))
                name_widget.bind(on_touch_up=lambda instance, touch, idx=index, n=name: self.on_press_up(instance, touch, idx, n))
            
            delete_btn = Button(text="X", size_hint_x=0.15, background_color=(0.9, 0.2, 0.2, 1))
            delete_btn.bind(on_press=lambda instance, idx=index: self.remove_file_name(idx))
            
            row_layout.add_widget(name_widget)
            row_layout.add_widget(delete_btn)
            self.grid_layout.add_widget(row_layout)

    def remove_file_name(self, index):
        if index < len(self.file_names):
            removed_name = self.file_names.pop(index)
            self.completed_photos.discard(removed_name)
            self.photo_uris.pop(removed_name, None)
            self.refresh_buttons()

    def on_press_down(self, instance, touch, index):
        if instance.collide_point(*touch.pos):
            touch.grab(instance)
            self.press_hold_event = Clock.schedule_once(lambda dt: self.trigger_long_press(index), 0.6)
            return True
        return False

    def on_press_up(self, instance, touch, index, name):
        if touch.grab_current is instance:
            touch.ungrab(instance)
            if self.press_hold_event:
                Clock.unschedule(self.press_hold_event)
                self.press_hold_event = None
                if instance.collide_point(*touch.pos):
                    if name in self.completed_photos and self.is_photo_available(name):
                        self.view_stored_photo(name)
                    else:
                        self.capture_photo(name)
            return True
        return False

    def trigger_long_press(self, index):
        self.press_hold_event = None
        self.editing_index = index
        self.refresh_buttons()

    def check_focus_lost(self, instance, value, index):
        if not value and self.editing_index == index:
            self.save_edited_name(index, instance.text)

    def save_edited_name(self, index, new_value):
        if self.editing_index == -1:
            return
        clean_value = new_value.strip().replace(" ", "_")
        if clean_value and index < len(self.file_names):
            old_name = self.file_names[index]
            if old_name in self.completed_photos:
                self.completed_photos.discard(old_name)
                self.completed_photos.add(clean_value)
                if old_name in self.photo_uris:
                    self.photo_uris[clean_value] = self.photo_uris.pop(old_name)
            self.file_names[index] = clean_value
        self.editing_index = -1  
        Window.release_keyboard()
        Clock.schedule_once(lambda dt: self.refresh_buttons(), 0.05)

    def add_custom_name(self, instance):
        text = self.new_name_input.text.strip().replace(" ", "_")
        if text and text not in self.file_names:
            self.file_names.append(text)
            self.refresh_buttons()
            self.new_name_input.text = ""

    def is_photo_available(self, name):
        stored_uri_string = self.photo_uris.get(name)
        if not stored_uri_string:
            return False
        if platform == 'android':
            try:
                from jnius import autoclass
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                context = PythonActivity.mActivity.getApplicationContext()
                content_resolver = context.getContentResolver()
                target_uri = Uri.parse(stored_uri_string)
                pfd = content_resolver.openFileDescriptor(target_uri, "r")
                if pfd is not None:
                    pfd.close()
                    return True
            except Exception:
                return False
        else:
            return stored_uri_string == "pc_dummy_path"
        return False

    def capture_photo(self, name):
        if self.editing_index != -1:
            return
        final_filename = f"{name}.jpg"
        self.status_label.text = f"Opening camera for: {final_filename}"
        
        if platform == 'android':
            try:
                from jnius import autoclass, cast
                Intent = autoclass('android.content.Intent')
                MediaStore = autoclass('android.provider.MediaStore')
                ContentValues = autoclass('android.content.ContentValues')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                MediaColumns = autoclass('android.provider.MediaStore$MediaColumns')
                ImagesMedia = autoclass('android.provider.MediaStore$Images$Media')
                
                current_activity = PythonActivity.mActivity
                context = current_activity.getApplicationContext()
                content_resolver = context.getContentResolver()
                
                values = ContentValues()
                values.put(MediaColumns.DISPLAY_NAME, final_filename)
                values.put(MediaColumns.MIME_TYPE, "image/jpeg")
                values.put(MediaColumns.RELATIVE_PATH, f"DCIM/{self.folder_name}")
                
                image_uri = content_resolver.insert(ImagesMedia.EXTERNAL_CONTENT_URI, values)
                self.photo_uris[name] = image_uri.toString()
                self.completed_photos.add(name)
                self.refresh_buttons()
                
                intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                parcelable_uri = cast('android.os.Parcelable', image_uri)
                intent.putExtra(MediaStore.EXTRA_OUTPUT, parcelable_uri)
                current_activity.startActivityForResult(intent, 1)
            except Exception as e:
                self.status_label.text = f"Error: {str(e)}"
        else:
            self.photo_uris[name] = "pc_dummy_path"
            self.completed_photos.add(name)
            self.refresh_buttons()
            self.status_label.text = f"[PC Mode] Simulated capture: {final_filename}"

    def view_stored_photo(self, name):
        stored_uri_string = self.photo_uris.get(name)
        if platform == 'android':
            try:
                from jnius import autoclass
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                target_uri = Uri.parse(stored_uri_string)
                intent = Intent(Intent.ACTION_VIEW)
                intent.setDataAndType(target_uri, "image/*")
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                PythonActivity.mActivity.startActivity(intent)
                self.status_label.text = f"Showing: {name}.jpg"
            except Exception as e:
                self.status_label.text = f"Could not open file: {str(e)}"
        else:
            self.status_label.text = f"[PC Mode] Displaying: {name}.jpg"

    def generate_pdf_report(self, instance):
        if not self.completed_photos:
            self.status_label.text = "Error: Please take at least 1 photo first!"
            return

        pdf_filename = f"{self.folder_name}_Report.pdf"
        self.status_label.text = "Compiling PDF..."

        if platform == 'android':
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                ContentValues = autoclass('android.content.ContentValues')
                MediaColumns = autoclass('android.provider.MediaStore$MediaColumns')
                DownloadsMedia = autoclass('android.provider.MediaStore$Downloads')
                
                context = PythonActivity.mActivity.getApplicationContext()
                content_resolver = context.getContentResolver()

                values = ContentValues()
                values.put(MediaColumns.DISPLAY_NAME, pdf_filename)
                values.put(MediaColumns.MIME_TYPE, "application/pdf")
                values.put(MediaColumns.RELATIVE_PATH, "Download/")
                
                pdf_uri = content_resolver.insert(DownloadsMedia.EXTERNAL_CONTENT_URI, values)
                pfd = content_resolver.openFileDescriptor(pdf_uri, "w")
                
                temp_path = os.path.join(context.getCacheDir().getAbsolutePath(), "temp_report.pdf")
                self._build_pdf_file(temp_path)
                
                with open(temp_path, "rb") as src:
                    pdf_bytes = src.read()
                
                FileOutputStream = autoclass('java.io.FileOutputStream')
                fos = FileOutputStream(pfd.getFileDescriptor())
                fos.write(pdf_bytes)
                fos.close()
                pfd.close()

                self.status_label.text = f"Saved to Phone -> Downloads/{pdf_filename}"
            except Exception as e:
                self.status_label.text = f"Android PDF Error: {str(e)}"
        else:
            pc_path = os.path.join(os.getcwd(), pdf_filename)
            try:
                self._build_pdf_file(pc_path)
                self.status_label.text = f"[PC Mode] PDF Generated at: {pdf_filename}"
            except Exception as e:
                self.status_label.text = f"PC Error: {str(e)}"

    def _build_pdf_file(self, target_filepath):
        doc = SimpleDocTemplate(target_filepath, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        story = []

        title_style = styles['Heading1']
        title_style.alignment = 1  
        story.append(Paragraph(f"Inspection Report: {self.folder_name.replace('_', ' ')}", title_style))
        story.append(Spacer(1, 15))

        for name in self.file_names:
            if name in self.completed_photos:
                label_style = styles['Heading2']
                story.append(Paragraph(f"Photo: {name.replace('_', ' ')}", label_style))
                story.append(Spacer(1, 6))

                if platform == 'android':
                    try:
                        from jnius import autoclass
                        Uri = autoclass('android.net.Uri')
                        PythonActivity = autoclass('org.kivy.android.PythonActivity')
                        context = PythonActivity.mActivity.getApplicationContext()
                        
                        uri_string = self.photo_uris[name]
                        target_uri = Uri.parse(uri_string)
                        
                        temp_img_path = os.path.join(context.getCacheDir().getAbsolutePath(), f"temp_{name}.jpg")
                        stream = context.getContentResolver().openInputStream(target_uri)
                        
                        import io
                        buffer = io.BytesIO()
                        chunk = stream.read()
                        while chunk != -1:
                            buffer.write(bytes([chunk]))
                            chunk = stream.read()
                        stream.close()

                        with open(temp_img_path, "wb") as f:
                            f.write(buffer.getvalue())

                        img_widget = Image(temp_img_path, width=450, height=330)
                        story.append(img_widget)
                    except Exception as e:
                        story.append(Paragraph(f"[Failed to process image: {str(e)}]", styles['Normal']))
                else:
                    story.append(Paragraph("[Image Content Data Simulated]", styles['Normal']))
                
                story.append(Spacer(1, 20))

        doc.build(story)

if __name__ == '__main__':
    CameraRenamerApp().run()
