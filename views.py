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
from django.db.models.query import QuerySet
from django.db.models.manager import Manager
# Renderers
def renderGallery(request, gallery=None, children=None, childrenFilter={}, photos=None, photosFilter={}):
    """Renders a gallery, subgalleries, and/or photos"""

    if gallery is None and children is None and photos is None:
        return galleryRoot(request)

    if photos is None:
        if gallery: photos = gallery.photo_children
        else: photos = []
    if children is None:
        if gallery: children = gallery.gallery_children
        else: gallery = []

    if isinstance(photos, QuerySet) or isinstance(photos, Manager): photos = filterquery(request, photos, **photosFilter).select_related()
    if isinstance(children, QuerySet) or isinstance(children, Manager): children = filterquery(request, children, **childrenFilter).select_related()

    staff=request.user.is_staff
    if staff or gallery is None or gallery.publicAncestry:
        for c in children:
            c.pickSamples(count=SAMPLE_SIZE, public= not staff)
        return render_to_response('galleria/gallery_detail.html', {'gallery':gallery, 'children':children, 'photos':photos, 'staff':staff, 'request':request})
    raise Http404

def renderPhoto(request, photo):
    staff=request.user.is_staff
    if staff or photo.publicAncestry:
        prevn = photo.get_previous_n(public=not staff)
        nextn = photo.get_next_n(public = not staff)
        if nextn: next = nextn[0]
        else: next = None
        if prevn: prev = prevn[prevn.count()-1]
        else: prev = None
        return render_to_response('galleria/photo_detail.html', {'photo':photo, 'staff':staff, 'request':request, 'next':next, 'prev':prev, 'nextn':nextn, 'prevn':prevn})
    raise Http404


# Parsers
def galleryRoot(request):
    return renderGallery(request, children=list(filterquery(request, AutoCollection.objects)) + list(filterquery(request, Folder.objects, parent=None)), photos=Photo.objects, photosFilter={'parent':None})

def folderparse(request, path):
    return renderGallery(request,gallery=folderFromPath(path))
    
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
    if len(pathlist)==1:
        try:
            return renderGallery(request, gallery=AutoCollection.objects.get(slug=pathlist[0]))
        except AutoCollection.DoesNotExist:
            pass
    children = Folder.objects.filter(parent=None).select_related()
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
    return renderGallery(request, gallery=folder)


# Utilities
def filterquery(request, query, **filt):
    """Handles default (and any custom) filtering on a QuerySet"""
    if not request.user.is_staff: filt['is_public']=True
    return query.filter(**filt)

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
 
