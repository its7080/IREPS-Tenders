import tkinter as tk
from tkinter import ttk, messagebox
import json
import os

class JSONEditor:
    def __init__(self, root, json_file, txt_file1):
        self.root = root
        self.root.title("Editor")
        self.json_file = json_file
        self.txt_file1 = txt_file1
        # self.txt_file2 = txt_file2  # Commented out
        self.data = self.load_json()

        self.entries = {}

        self.create_tabs()

    def load_json(self):
        if not os.path.exists(self.json_file):
            messagebox.showerror("Error", f"File {self.json_file} does not exist!")
            self.root.quit()
        with open(self.json_file, 'r') as file:
            return json.load(file)

    def save_json(self):
        with open(self.json_file, 'w') as file:
            json.dump(self.data, file, indent=4)
        messagebox.showinfo("Info", "JSON file saved successfully")

    def load_txt(self, txt_file):
        if not os.path.exists(txt_file):
            messagebox.showerror("Error", f"File {txt_file} does not exist!")
            self.root.quit()
        with open(txt_file, 'r') as file:
            return file.read()

    def save_txt(self, txt_editor, txt_file):
        with open(txt_file, 'w') as file:
            file.write(txt_editor.get("1.0", tk.END).strip())
        messagebox.showinfo("Info", "Text file saved successfully")

    def create_tabs(self):
        self.tab_control = ttk.Notebook(self.root)
        
        self.json_tab = ttk.Frame(self.tab_control)
        self.txt_tab1 = ttk.Frame(self.tab_control)
        # self.txt_tab2 = ttk.Frame(self.tab_control)  # Commented out
        self.help_tab = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.json_tab, text='Edit Configuration')
        self.tab_control.add(self.txt_tab1, text='Edit Organization List')
        # self.tab_control.add(self.txt_tab2, text='Edit Sheet Names')  # Commented out
        self.tab_control.add(self.help_tab, text='Help')
        
        self.tab_control.pack(expand=1, fill='both')
        
        self.create_json_form()
        self.create_txt_editor(self.txt_tab1, self.txt_file1)
        # self.create_txt_editor(self.txt_tab2, self.txt_file2)  # Commented out
        self.create_help_tab()

    def create_json_form(self):
        padding = {'padx': 10, 'pady': 5}
        label_font = ('Arial', 12)
        entry_font = ('Arial', 10)
        
        row = 0
        for key, value in self.data.items():
            label = tk.Label(self.json_tab, text=key, font=label_font)
            label.grid(row=row, column=0, sticky='w', **padding)
            
            if key in ("browser", "adb_device", "captcha_manual_input"):
                self.adb_device_var = tk.StringVar(value=str(value))
                enable_rb = tk.Radiobutton(self.json_tab, text="Enable", variable=self.adb_device_var, value="1", font=entry_font)
                disable_rb = tk.Radiobutton(self.json_tab, text="Disable", variable=self.adb_device_var, value="0", font=entry_font)
                enable_rb.grid(row=row, column=1, sticky='w', **padding)
                disable_rb.grid(row=row, column=2, sticky='w', **padding)
                self.entries[key] = self.adb_device_var
            elif isinstance(value, list):
                text = tk.Text(self.json_tab, height=4, width=80, font=entry_font)
                text.insert(tk.END, '\n'.join(value))
                text.grid(row=row, column=1, columnspan=2, **padding)
                self.entries[key] = text
            else:
                entry = tk.Entry(self.json_tab, width=80, font=entry_font)
                entry.insert(0, str(value))
                entry.grid(row=row, column=1, columnspan=2, **padding)
                self.entries[key] = entry
            row += 1
        
        save_button = tk.Button(self.json_tab, text="Save", command=self.update_json, font=('Arial', 12, 'bold'), bg='blue', fg='white')
        save_button.grid(row=row, column=0, columnspan=3, pady=20)

    def create_txt_editor(self, tab, txt_file):
        padding = {'padx': 10, 'pady': 5}
        entry_font = ('Arial', 10)
        
        txt_editor = tk.Text(tab, height=20, width=100, font=entry_font)
        txt_editor.pack(expand=1, fill='both', padx=padding['padx'], pady=padding['pady'])
        
        save_button = tk.Button(tab, text="Save", command=lambda: self.save_txt(txt_editor, txt_file), font=('Arial', 12, 'bold'), bg='blue', fg='white')
        save_button.pack(pady=20, padx=padding['padx'])
        
        txt_content = self.load_txt(txt_file)
        txt_editor.insert(tk.END, txt_content)

    def create_help_tab(self):
        padding = {'padx': 10, 'pady': 5}
        help_text = (
            "Instructions:\n\n"
            "1. Edit Configuration:\n"
            "   - Modify the values in the fields as needed.\n"
            "   - Click 'Save' to save changes to the JSON file.\n\n"
            "2. Edit Organization List:\n"
            "   - Modify the text content as needed.\n"
            "   - Maintain organization number and its name in a single line orientation.\n"
            "   - Put '#' before lines to ignore a particular organization.\n"
            "   - Click 'Save' to save changes to the organization list text file.\n\n"
            # "3. Edit Sheet Names:\n"  # Commented out
            # "   - Modify the text content as needed.\n"  # Commented out
            # "   - Put each seat name in a single line orientation.\n"  # Commented out
            # "   - Click 'Save' to save changes to the sheet names text file.\n\n"  # Commented out
            "4. Help:\n"
            "   - View these instructions for guidance on using the application."
        )
        help_label = tk.Label(self.help_tab, text=help_text, justify=tk.LEFT, font=('Arial', 12))
        help_label.pack(**padding)

    def update_json(self):
        for key, widget in self.entries.items():
            if key == "adb_device":
                self.data[key] = widget.get()
            elif isinstance(widget, tk.Text):
                self.data[key] = widget.get("1.0", tk.END).strip().split('\n')
            else:
                self.data[key] = widget.get()
        
        self.save_json()

if __name__ == "__main__":
    root = tk.Tk()
    json_file_path = 'Program_Files/Configration.json'
    txt_file1_path = 'Program_Files/Organization_list.txt'
    # txt_file2_path = 'Input_files/sheet_names.txt'  # Commented out
    app = JSONEditor(root, json_file_path, txt_file1_path)  # Modified
    root.mainloop()
