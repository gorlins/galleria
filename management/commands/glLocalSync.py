#!/usr/bin/python
# coding: utf-8
from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from galleria.models import *
import os
from datetime import datetime
from django.template.defaultfilters import slugify
from django.core.files.base import ContentFile
from django.core.files import File
from django.db import settings

class Command(BaseCommand):
    help = ('Updates exif information for all photos.')

    requires_model_validation = True
    can_import_settings = True

    def handle(self, *args, **options):
        return localsync(args, options)

def localsync(sizes, options):
    main()

LOCAL_ROOT = settings.GALLERIA_LOCAL_SYNC
VALID_FILES=['.jpg', '.jpeg', '.tif', '.tiff']
EXCLUDE_DIRS=['Originals', 'cache']
EXCLUDE_STARTSWITH=['_', '@', '.']
COPY_ALL = getattr(settings, 'GALLERIA_COPY_ALL', False)
DELETE_ORPHANS = getattr(settings, 'GALLERIA_DELETE_ORPHANS', True)
PRECACHE_NEW = getattr(settings, 'GALLERIA_PRECACHE_NEW', False)
CACHE_SUBDIR='.glcache'
GALLERIA_ROOT = getattr(settings, 'GALLERIA_ROOT', 'galleria')

SYMLINK = getattr(settings, 'GALLERIA_SYMLINK', True)

skipped = 0
added = 0
excluded=0
found = 0
modified = 0
from time import time
t = 0
orphaned = {}
orphaned_g = {}

def walkFolders(localdir, parent):
    global skipped
    global added
    global excluded
    global found
    global modified

    (path, foldername) = os.path.split(localdir)
    cachedir = os.path.join(localdir, CACHE_SUBDIR)
    if not os.path.isdir(cachedir):
        os.makedirs(cachedir)

    if parent is None:
        childFolders = Folder.objects.filter(parent=None).select_related()
        childPhotos = Photo.objects.filter(parent=None).select_related()
        parentabsdir = ''
    elif parent.id is None:
        # If folder isn't saved yet
        childFolders = models.query.EmptyQuerySet(model=Folder)
        childPhotos = models.query.EmptyQuerySet(model=Photo)
        parentabsdir = parent.folderpath()
    else:
        childFolders = parent.folder_children.all()
        childPhotos = parent.photo_children.all()
        parentabsdir = parent.folderpath()
    parentabsdir = os.path.join(settings.MEDIA_ROOT, GALLERIA_ROOT, parentabsdir)
    parentcache = os.path.join(parentabsdir, CACHE_SUBDIR)
    if not os.path.isdir(parentcache):
        if not os.path.isdir(parentabsdir):
            os.makedirs(parentabsdir)
        if not os.path.exists(parentcache):
            os.symlink(cachedir, parentcache)

    ls = os.listdir(localdir)
    ls.sort()
    isFolder = [os.path.isdir(os.path.join(localdir, f)) for f in ls]
    valid = False
    foundPhotos = []
    foundFolders = []
    for (isSubdir, f) in zip(isFolder, ls):
        if any([f.startswith(s) for s in EXCLUDE_STARTSWITH]):
            skipped+=1
            continue
        slug=slugify(f)
        thisf = os.path.join(localdir, f)
        if isSubdir:
            if f in EXCLUDE_DIRS:
                skipped += 1
                continue
            try:
                folder = childFolders.get(foldername=f)
            except Folder.DoesNotExist:
                try:
                    if parent.mustsave:
                        parent.save()
                        parent.mustsave = False
                except AttributeError:
                    pass
                folder = Folder(title=f, slug=slug, foldername=f, parent=parent)
                folder.mustsave=True#save() # Will save if any folders are added
                print '+F', folder.folderpath()
            fvalid = walkFolders(thisf, folder)
  
            if fvalid:
                foundFolders.append(f)
            valid = valid or fvalid
                
        else:
            (im, ext) = os.path.splitext(f)
            setPublic = None
            if not ext.lower() in VALID_FILES:
                skipped += 1
                continue
            try:
                photo = childPhotos.get(slug=slug)
                (ppath, pbase) = os.path.split(photo.image.path)
                if not f == pbase: # Some file modification, eg ss.jpg -> ss_.jpg
                    print '!!', f, pbase
                    setPublic = photo.is_public
                    photo.delete()
                    raise Photo.DoesNotExist()
                found += 1
                ps = os.stat(thisf)
                ds = os.stat(photo.display.image.fp.name)
                if ps.st_mtime > ds.st_mtime:
                    print '~', photo.folderpath(), ':', photo.title
                    modified+=1
                    if not os.path.islink(thisf):
                        photo.image.save(photo.title, ContentFile(open(thisf).read()), save=False)
                    photo.save(clear_cache=True)

            except Photo.DoesNotExist:
                (name, ext) = os.path.splitext(f)
                if name[-1] == '_':
                    print '!?', 'Found bogus file ' + f
                    os.remove(thisf)
                    continue
                try:
                    if parent.mustsave:
                        parent.save()
                        parent.mustsave=False # Prevents unnecessary saving
                except AttributeError:
                    pass
                kwds = dict(uploadName=f, title=f, parent=parent, symlink=SYMLINK, slug=slug, preCache=PRECACHE_NEW)
                if not setPublic is None:
                    kwds['is_public'] = setPublic
                #try:
                print thisf
                photo = Photo.create(thisf, **kwds)
                print '+', photo.folderpath(), ':', photo.title

                added+=1
                #except Exception:
                #    print 'Error with ' + f
            valid=True
            foundPhotos.append(slug)

    # Delete orphans
    for p in childPhotos.exclude(slug__in=foundPhotos):
        print '-', p.folderpath(), ':', p.title
        p.delete()
    
    for f in childFolders.exclude(foldername__in=foundFolders):
        print '-F', f.folderpath()
        f.delete()

    # Delete this folder if invalid
    if valid and not parent is None:
        parent.save()
    elif (not valid) and (not parent is None) and parent.id is None:
        print '-F', parent.folderpath(), 'Empty'
        #parent.delete()#is this necessary with the above foundFolders??
        pass
    return valid

def main():
    (sampledir, junk) = os.path.split(__file__)
    t = time()
    valid = walkFolders(LOCAL_ROOT, None)
    t = time()-t
    print "Localsync completed successfully from %s"%LOCAL_ROOT
    print "Added %i and found %i current photos"%(added, found)
    print "Updated %i modified photos"%modified
    print "Excluded %i dirs and images"%skipped
    print "took %s seconds"%t
    
