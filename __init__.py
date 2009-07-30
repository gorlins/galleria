from django.http import HttpResponse
from django.template.defaultfilters import slugify
import os
from django.shortcuts import render_to_response
from django.http import Http404
#from django.conf import settings
from galleria.models import Folder, Photo
from django.contrib.auth.decorators import login_required

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
 
def renderGallery(request, gallery):
    staff=request.user.is_staff()
    if staff or gallery.publicAncestry():
        return render_to_response('galleria/gallery_detail.html', {'gallery':gallery, 'staff':staff, 'request':request})
    raise Http404

def renderPhoto(request, photo):
    staff=request.user.is_staff()
    if staff or gallery.publicAncestry():
        return render_to_response('galleria/photo_detail.html', {'photo':photo, 'staff':staff, 'request':request})
    raise Http404

def folderparse(request, path):
    renderGallery(request,folderFromPath(path))
    
def photoparse(request, path, photo):
    try:
        p = folder.photo_children.get(slug=photo)
        renderPhoto(request, p)
    except Photo.DoesNotExist:
        raise Http404

def galleryRoot(request):
    staff = request.user.is_staff()
    return render_to_response('galleria/gallery_root.html', {'folders':Folder.objects.filter(parent=None, is_public__in=[True, not staff]),
                                                              'photos':Photo.objects.filter(parent=None, is_public__in=[True, not staff]),
                                                              'staff':staff, 'request':request})

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
                    renderPhoto(request, photo)
                    
                except Photo.DoesNotExist:
                    raise Http404
            raise Http404
    renderGallery(request, folder)

