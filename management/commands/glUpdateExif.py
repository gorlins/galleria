from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from galleria.models import *

class Command(BaseCommand):
    help = ('Updates exif information for all photos.')

    requires_model_validation = True
    can_import_settings = True

    def handle(self, *args, **options):
        return update_exif(args, options)

def update_exif(sizes, options):
    """
    Updates all exif information
    """
    map(Photo.reloadExif, Photo.objects.all())
    map(Folder.save, Folder.objects.all())
