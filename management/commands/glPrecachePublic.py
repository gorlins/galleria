from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from galleria.models import *

class Command(BaseCommand):
    help = ('Updates exif information for all photos.')

    requires_model_validation = True
    can_import_settings = True

    def handle(self, *args, **options):
        return precache(args, options)

def precache(sizes, options):
    """
    Updates all exif information
    """
    for folder in Folder.objects.filter(is_public=True):
        print folder.folderpath()
        for photo in folder.public():
            #print photo.folderpath(), photo.title
            photo._pre_cache()
