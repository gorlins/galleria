import os
from django.core.files.storage import FileSystemStorage

class OverwritingStorage(FileSystemStorage):
    def _save(self, name, content):
        full_path = self.path(name)
        if os.path.exists(full_path):
            os.remove(full_path)
        return FileSystemStorage._save(self, name, content)

    def get_available_name(self, name):
        return name
