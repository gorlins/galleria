from django.conf import settings
from django.conf.urls.defaults import *
from galleria.models import *
#from galleria.views import photoparse, urlparse, galleryRoot

# Number of random images from the gallery to display.
SAMPLE_SIZE = ":%s" % getattr(settings, 'GALLERY_SAMPLE_SIZE', 5)

# galleries
urlpatterns = patterns('',
                       url(r'^$', 'galleria.views.galleryRoot', name='gl-galleryRoot'),
                       url(r'^gallery/(?P<path>.*)$', 'galleria.views.urlparse', name='gl-gallery'),
                       url(r'^photo/(?P<path>.*)/(?P<photo>[^/]*)$', 'galleria.views.photoparse', name='gl-photo'),
                       )

