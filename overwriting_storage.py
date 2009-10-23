import os

from django.conf import settings
from django.core.files import locks, File
from django.core.files.storage import FileSystemStorage

class OverwritingStorage(FileSystemStorage):
    def _save(self, name, content):
        full_path = self.path(name)

        directory = os.path.dirname(full_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        elif not os.path.isdir(directory):
            raise IOError("%s exists and is not a directory." % directory)

        # There's a potential race condition between get_available_name and
        # saving the file; it's possible that two threads might return the
        # same name, at which point all sorts of fun happens. So we need to
        # try to create the file, but if it already exists we have to go back
        # to get_available_name() and try again.

        while True:
            try:
                # This file has a file path that we can move.
                if hasattr(content, 'temporary_file_path'):
                    file_move_safe(content.temporary_file_path(), full_path)
                    content.close()

                # This is a normal uploadedfile that we can stream.
                else:
                    # This fun binary flag incantation makes os.open throw an
                    # OSError if the file already exists before we open it.
                    fd = os.open(full_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0))
                    try:
                        locks.lock(fd, locks.LOCK_EX)
                        for chunk in content.chunks():
                            os.write(fd, chunk)
                    finally:
                        locks.unlock(fd)
                        os.close(fd)
            except OSError, e:
                if e.errno == errno.EEXIST:
                    # Ooops, the file exists. We need a new file name.
                    #name = self.get_available_name(name)
                    #full_path = self.path(name)
                    os.remove(full_path)
                else:
                    raise
            else:
                # OK, the file save worked. Break out of the loop.
                break
        
        if settings.FILE_UPLOAD_PERMISSIONS is not None:
            os.chmod(full_path, settings.FILE_UPLOAD_PERMISSIONS)
        
        return name

