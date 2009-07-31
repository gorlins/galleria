from django.http import HttpResponse
from django.template.defaultfilters import slugify
import os
from django.shortcuts import render_to_response
from django.http import Http404
#from django.conf import settings
from galleria.models import *
from django.contrib.auth.decorators import login_required
from django.conf import settings
SAMPLE_SIZE = getattr(settings, 'GALLERY_SAMPLE_SIZE', 3)
# Renderers
def renderGallery(request, gallery=None, children=None, photos=None):
    if gallery is None and children is None and photos is None:
        return galleryRoot(request)
    staff=request.user.is_staff
    if gallery and children is None:
        children = gallery.gallery_children.all()
    if gallery and photos is None:
        photos = gallery.photo_children.all()
    if not staff:
        photos = photos.filter(is_public=True)
        children = children.filter(is_public=True)
    if staff or gallery is None or gallery.publicAncestry:
        for c in children:
            c.pickSamples(count=SAMPLE_SIZE, public= not staff)
        return render_to_response('galleria/gallery_detail.html', {'gallery':gallery, 'children':children, 'photos':photos, 'staff':staff, 'request':request})
    raise Http404

def renderPhoto(request, photo):
    staff=request.user.is_staff
    if staff or photo.publicAncestry:
        return render_to_response('galleria/photo_detail.html', {'photo':photo, 'staff':staff, 'request':request})
    raise Http404


# Parsers
def galleryRoot(request):
    return renderGallery(request, children=Folder.objects.filter(parent=None), photos=Photo.objects.filter(parent=None))

def folderparse(request, path):
    return renderGallery(request,folderFromPath(path))
    
def photoparse(request, path, photo):
    try:
        p = folder.photo_children.get(slug=photo)
        return renderPhoto(request, p)
    except Photo.DoesNotExist:
        raise Http404

def urlparse(request, path=None):
    if path == '':
        return galleryRoot(request)
    pathlist = path.split('/')
    children = Folder.objects.filter(parent=None)
    pathlist.reverse()
    folder = None
    
    while len(pathlist):
        slug = pathlist.pop()
        try:
            folder = children.get(slug=slug)
            children = folder.folder_children
        except Folder.DoesNotExist:
            if len(pathlist) == 0:
                try:
                    if folder is None:
                        photo = Photo.objects.filter(parent=None).get(slug=slug)
                    else:
                        photo = folder.photo_children.get(slug=slug)
                    return renderPhoto(request, photo)
                    
                except Photo.DoesNotExist:
                    raise Http404
            raise Http404
    return renderGallery(request, folder)


# Utilities
def folderFromPath(path):
    pathlist = path.split('/')
    folder = None
    children = Folder.objects.filter(parent=None)
    while len(pathlist):
        slug = pathlist.pop()
        try:
            folder = children.get(slug=slug)
            children = folder.folder_children
        except Folder.DoesNotExist:
            raise Http404
    return folder
 
