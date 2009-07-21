from django.http import HttpResponse
from django.template.defaultfilters import slugify
import os
from django.shortcuts import render_to_response
from django.http import Http404
#from django.conf import settings
from galleria.models import Folder, Photo

#SAMPLE_SIZE = ":%s" % getattr(settings, 'GALLERY_SAMPLE_SIZE', 3)

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
     
def folderparse(request, path):
    return render_to_response('galleria/folder_detail.html', {'folder':folderFromPath(path), 'authenticated':authenticated})

def photoparse(request, path, photo):
    folder = folderFromPath(path)
    try:
        p = folder.photo_children.get(slug=photo)
        return render_to_response('galleria/photo_detail.html', {'photo':p, 'authenticated':authenticated})
    except Photo.DoesNotExist:
        raise Http404

def galleryRoot(request):
    authenticated = request.user.is_authenticated()
    public = not authenticated
    return render_to_response('galleria/gallery_root.html', {'folders':Folder.objects.filter(parent=None, is_public__in=[True, public]),
                                                              'photos':Photo.objects.filter(parent=None, is_public__in=[True, public]),
                                                              'authenticated':authenticated,
                                                              })
def urlparse(request, path=None):
    #(path, im) = os.path.split(gallery)
    if path == '':
        return galleryRoot(request)
    authenticated = request.user.is_authenticated()
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
                    return render_to_response('galleria/photo_detail.html', {'photo':photo, 'authenticated':authenticated})
                except Photo.DoesNotExist:
                    raise Http404
            raise Http404
    #return HttpResponse('found folder %s, %s, %s'%(folder.relpath(), folder.title, folder.slug))
    return render_to_response('galleria/folder_detail.html', {'folder':folder, 'authenticated':authenticated})

