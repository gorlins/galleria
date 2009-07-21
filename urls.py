from django.conf import settings
from django.conf.urls.defaults import *
from galleria.models import *
from galleria import folderparse, photoparse, urlparse, galleryRoot

# Number of random images from the gallery to display.
SAMPLE_SIZE = ":%s" % getattr(settings, 'GALLERY_SAMPLE_SIZE', 5)

# galleries
urlpatterns = patterns('',
                       url(r'^$', galleryRoot, name='gl-galleryRoot'),
                       url(r'^gallery/(?P<path>.*)', urlparse, name='gl-gallery'),
                       url(r'^photo/(?P<path>.*)/(?P<photo>[^/]*)', photoparse, name='gl-photo'),
                       )
"""
urlpatterns += patterns('django.views.generic.list_detail',
    url(r'^gallery/(?P<inputrequest>.*)', urlparse)
    url(r'^gallery/(?P<', 'object_detail', {'slug_field': 'title_slug', 'queryset': Gallery.objects.filter(is_public=True), 'extra_context':{'sample_size':SAMPLE_SIZE}}, name='gl-gallery'),
    url(r'^$', 'object_list', {'queryset': Gallery.objects.filter(is_public=True, parent=None), 'allow_empty': True, 'paginate_by': 10000, 'extra_context':{'sample_size':SAMPLE_SIZE}}),
)

# photographs
photo_args = {'date_field': 'date_taken', 'allow_empty': True, 'queryset': Photo.objects.filter(is_public=True)}
urlpatterns += patterns('django.views.generic.list_detail',
    url(r'^photo/(?P<slug>[\-\d\w]+)/$', 'object_detail', {'slug_field': 'title_slug', 'queryset': Photo.objects.filter(is_public=True)}, name='gl-photo'),
    url(r'^photo/page/(?P<page>[0-9]+)/$', 'object_list', {'queryset': Photo.objects.filter(is_public=True), 'allow_empty': True, 'paginate_by': 20}, name='gl-photo-list'),
)

"""
