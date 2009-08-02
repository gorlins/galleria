from django.conf import settings
from django.db import models

# Create your models here.
from django.core.urlresolvers import reverse
from imagekit.models import ImageModel
from django.utils.translation import ugettext_lazy as _ #retarded hack from photologue
from datetime import datetime
import os
import random
from utils import EXIF
from galleria.symlinkstorage import SymlinkStorage
from galleria.specs import Preprocess
from django.core.files.base import ContentFile, File
from StringIO import StringIO
import subprocess
import operator
from django.db.models import F


GALLERIA_ROOT = getattr(settings, 'GALLERIA_ROOT', 'galleria')
SAMPLE_SIZE = getattr(settings, 'GALLERY_SAMPLE_SIZE', 3)
PRIVATE_IPS = getattr(settings, 'GALLERIA_PRIVATE_IPS', ['none'])

# Utilities
def uploadFolder(photo, filename):
    return os.path.join(GALLERIA_ROOT, photo.folderpath(), filename)

class RestrictedQuerySet(models.query.QuerySet):
    def __init__(self, filterParent=False, **kwargs):
        models.query.QuerySet.__init__(self, **kwargs)
        self._filterparent=filterParent
        
    def getRestricted(self, user, **filt):
        """Handles default (and any custom) filtering on a QuerySet, restricting
        accesss to objects based on user"""
        if not user is None and not user.is_staff:
            filt['is_public']=True
            if self._filterparent:
                filt['parent__is_public']=True
        return self.filter(**filt)
    
class RestrictedManager(models.Manager):
    
    def __init__(self, filterParent=False, **kwargs):
        self._filterparent=filterParent
        models.Manager.__init__(self, **kwargs)
        
    def get_query_set(self):
        filterParent = self._filterparent
        return RestrictedQuerySet(self, filterParent=filterParent, model=self.model)
    
    def getRestricted(self, user, **filt):
        """Handles default (and any custom) filtering on a QuerySet, restricting
        accesss to objects based on user"""
        
        return self.get_query_set().getRestricted(user, **filt)

# Models
class Photo(ImageModel):
    title = models.CharField(max_length=100)
    slug = models.SlugField(_('title slug'), max_length=60, help_text=_('A "slug" is a URL-friendly title for an object.'))
    caption = models.CharField(_('caption'), max_length=60, blank=True, default='')
    image = models.ImageField(upload_to=uploadFolder)
    num_views = models.PositiveIntegerField(editable=False, default=0)
    date_added = models.DateTimeField(_('date published'), default=datetime.now)
    date_taken = models.DateTimeField(_('date taken'), default=datetime.now)
    parent = models.ForeignKey('Folder', related_name="photo_children", blank=True, null=True)
    is_public = models.BooleanField(_('is public'), default=True, help_text=_('Public photographs will be displayed in the default views.'))

    objects = RestrictedManager(filterParent=True)
    
    class Meta:
        ordering = ['date_taken', 'slug']
        get_latest_by = '-date_taken'
        verbose_name = _('photograph')
        verbose_name_plural = _('photographs')

    class IKOptions:
        # This inner class is where we define the ImageKit options for the model
        spec_module = 'galleria.specs'
        cache_dir = ''
        image_field = 'image'
        save_count_as = 'num_views'
        cache_filename_format = ".glcache/%(specname)s/%(filename)s.%(extension)s"
    #preprocessor = Preprocess

    EXIF_ORIENTATION_STEPS = {
        1: [],
        2: ['FLIP_LEFT_RIGHT'],
        3: ['ROTATE_180'],
        4: ['FLIP_TOP_BOTTOM'],
        5: ['ROTATE_270', 'FLIP_LEFT_RIGHT'],
        6: ['ROTATE_270'],
        7: ['ROTATE_90', 'FLIP_LEFT_RIGHT'],
        8: ['ROTATE_90'],
    }

    @classmethod
    def create(cls, filename, uploadName=None, preCache=False, symlink=True, **kwargs):
        from PIL import Image
        p = cls(**kwargs)
        if uploadName is None:
            uploadName = os.path.basename(filename)
        #print filename
        # Auto rotates the image with ImageMagick
        rotate=False
        try:
            orientation = p.EXIF['Image Orientation']
            rotate=True
        except (KeyError, TypeError):
            try:
                orientation = Image.open(filename)._getexif()[0x0112]
                rotate = True
            except (KeyError, TypeError):
                pass

        if rotate and orientation > 1:
            print "Autorotating %s from orientation %i"%(uploadName, orientation)
            #subprocess.call('convert -auto-orient "%s" "%s"'%(filename, filename), shell=True)
            subprocess.call('exifautotran %s'%filename, shell=True)
            
        s = open(filename, 'rb')
        if symlink:
            p.image.save(uploadName, ContentFile(''), save=False) #Just enough info for header (?)
            upload = p.image.path
            os.remove(upload)
            os.symlink(filename, upload)
            p.save(clear_cache=True)
            if preCache:
                p._pre_cache()
        else:
            p.image.save(uploadName, ContentFile(s.read()), save=False)
            p.save(clear_cache=True)
        return p

    def __unicode__(self):
        return self.title

    def admin_thumb(self):
        return '<img src="%s"/>'%self.smallthumb.url
    admin_thumb.short_description = _('Thumbnail')
    admin_thumb.allow_tags = True

    def get_absolute_url(self):
        return reverse('gl-gallery', kwargs={'path':os.path.join(self.relpath(), self.slug)})
    
    @property
    def printcaption(self):
        if self.caption is None or self.caption == 'None' or self.caption == '':
            return self.title
        return self.caption

    def get_next_n(self, n=4, user=None, field='date_taken'):
        filt={(field+'__gte'):getattr(self, field), 'slug__gt':self.slug}
        return self.parent.photo_children.getRestricted(user, **filt).order_by(field, 'slug')[:n]

    def get_previous_n(self, n=4, user=None, field='date_taken'):
        filt={(field+'__lte'):getattr(self, field), 'slug__lt':self.slug}
        ps = self.parent.photo_children.getRestricted(user, **filt).order_by(field, 'slug')
        count = ps.count()
        return ps[max(0, count-n):count]

    def get_next(self, user=None, field='date_taken'):
        a=self.get_next_n(n=1, user=user, field=field)
        try:
            return a[0]
        except IndexError:
            return None

    def get_previous(self, user=None, field='date_taken'):
        a = self.get_previous_n(n=1, user=user, field=field)
        try:
            return a[0]
        except IndexError:
            return None

    @property
    def EXIF(self):
        try:
            return EXIF.process_file(open(self.image.path, 'rb'))
        except:
            try:
                return EXIF.process_file(open(self.image.path, 'rb'), details=False)
            except:
                return {}
    def reloadExif(self, resave=True, clear_cache=False):
        try:
            exif = self.EXIF
            exif_date = exif['EXIF DateTimeOriginal'].values # want error if it doesn't have key
            
        except (TypeError, KeyError):
            from PIL import Image
            try:
                exif = Image.open(open(self.image.path, 'rb'))._getexif()
                exif_date=exif[0x9003]
            except (TypeError, KeyError):
                # Fallback to file creation time
                s = os.stat(self.image.path)
                self.date_taken = datetime.fromtimestamp(s.st_ctime)
                exif_date = None
        
        if exif_date is not None:
            try:
                d, t = str.split(exif_date)
                year, month, day = d.split(':')
                hour, minute, second = t.split(':')
                self.date_taken = datetime(int(year), int(month), int(day),
                                           int(hour), int(minute), int(second))    
            except ValueError:
                pass
        if self.caption is None or self.caption in ['', 'None'] or self.caption.startswith('['):
            try:
                c = str(exif['EXIF UserComment'].printable).strip() # Doesn't overwrite user-added captions
                if not c.startswith('['):
                    self.caption = c
                else:
                    self.caption=''
            except (KeyError, TypeError):
                self.caption=''
        if resave:
            self.save(clear_cache=clear_cache)

    def ancestry(self):
        if self.parent is None:
            return []
        return self.parent.ancestry(includeSelf=True)

    def save(self, *args, **kwargs):
        self.reloadExif(resave=False)
        if not 'clear_cache' in kwargs:
            kwargs['clear_cache']=False # alters default
        ImageModel.save(self, *args, **kwargs)

    @property
    def publicAncestry(self):
        """Returns True if self and all parents are public"""
        objs = self.ancestry()
        objs.append(self)
        return all([obj.is_public for obj in objs])
  

    def abspath(self):
        return self.image.file

    def relpath(self):
        """The relative directory of this photo, given it's parent
        Safely handles case of no parent
        """
        if self.parent is None:
            rel = ''
        else:
            rel = self.parent.relpath(includeSelf=True)
        return rel
    def folderpath(self):
        """The folder directory of this photo, given it's parent
        Safely handles case of no parent
        """
        if self.parent is None:
            rel = ''
        else:
            rel = self.parent.folderpath(includeSelf=True)
        return rel

class Gallery(models.Model):
    title = models.CharField(_('title'), max_length=60)
    slug = models.SlugField(_('slug'), max_length=60,
                                  help_text=_('A "slug" is a URL-friendly title for an object.'))
    
    date_added = models.DateTimeField(_('date published'), default=datetime.now)
    date_beginning = models.DateTimeField(_('date of first photo'), default=datetime.now)
    
    description = models.TextField(_('description'), blank=True)
    is_public = models.BooleanField(_('is public'), default=False,
                                    help_text=_('Public galleries will be displayed in the default views.'))

    objects = RestrictedManager()
    
    class Meta:
        ordering = ['-date_beginning']
        get_latest_by = 'date_beginning'
        verbose_name = _('gallery')
        verbose_name_plural = _('galleries')
        abstract = True

    def __unicode__(self):
        return self.title

    def __str__(self):
        return self.__unicode__()

    def admin_thumb(self):
        return ''.join(['<img src="%s"/>'%im.smallthumb.url for im in self.sample(count=3)])

    admin_thumb.short_description = _('Thumbnail')
    admin_thumb.allow_tags = True

    def get_absolute_url(self):
        return reverse('gl-gallery', args=[self.slug])

    def pickSamples(self, count=0, user=None, force=False):
        self.samples = self.sample(count=count, user=user) 

    def sample(self, count=0, user=None):
        photo_set = self.photo_children.getRestricted(user)

        mycount = photo_set.count()

        if count > mycount or mycount==0:
            children = self.gallery_children.getRestricted(user)
            photo_set = reduce(operator.or_, [photo_set]+[g.photo_children.getRestricted(user) for g in children])
        if count==0: pick = photo_set.count()
        else: pick = count
        return photo_set.order_by('-num_views')[:pick]

    def photo_count(self, user=None):
        p = self.photo_children.getRestricted(user)
        return p.count()
    photo_count.short_description = _('count')
    
    def save(self, *args, **kwargs):
        if self.photo_children.count():
            self.date_beginning = self.photo_children.order_by('date_taken')[0].date_taken
            pass
        models.Model.save(self, *args, **kwargs)

class Folder(Gallery):
    """Directory structure-like album, where every photo must live in one
    and only one folder, and folders may have heirarchy
    For arbitrary photo collection, see Collection
    Overloads Gallery to do things like traverse the heirarchy, store photos
    in subfolders, and delete child photos when deleted
    """

    foldername = models.CharField(_('folder name'), max_length=60, help_text=_('A non-changing name for the folder'), null=False, blank=False)
    parent = models.ForeignKey('self', related_name='folder_children', null=True, blank=True)
    
    objects = RestrictedManager(filterParent=True)
    
    @property
    def gallery_children(self):
        return self.folder_children

    class Meta:
        verbose_name = _('folder')
        verbose_name_plural = _('folders')

    def get_absolute_url(self):
        return reverse('gl-gallery', kwargs={'path':self.relpath()})

    def walk_ancestry(self):
        """Iterates over the ancestors of self, starting with self and going up"""
        f = self
        while not f is None:
            yield f
            f = f.parent
 
    def delete(self):
        import shutil
        folder = os.path.join(settings.MEDIA_ROOT, uploadFolder(self, ''))
        Gallery.delete(self)
        try:
            os.remove(os.path.join(folder, '.htaccess'))
        except OSError:
            pass
        try:
            shutil.rmtree(folder)
        except OSError:
            pass
 
    def ancestry(self, includeSelf=False):
        """Returns a list of all folders in this folder's path, including self as the last element"""
        path = [f for f in self.walk_ancestry()]
        path.reverse()
        if not includeSelf:
            path.pop()
        return path

    def htaccess(self):
        global PRIVATE_IPS
        f = open(os.path.join(self.abspath(), '.htaccess'), 'w')
        if not self.is_public:
            f.write('Order Deny,Allow\nDeny from all\n')
            if not operator.isSequenceType(PRIVATE_IPS):
                PRIVATE_IPS = [PRIVATE_IPS]
            f.writelines(['Allow from %s\n'%ip for ip in PRIVATE_IPS if (not ip is None or ip=='')])
            f.write('Satisfy Any\n')
        else:
            f.writelines(['<Files "%s">\nDeny from all\n</Files>\n'%p.title for p in self.photo_children.filter(is_public=False)])
        f.close()
        
    def folderpath(self, includeSelf=True):
        return os.path.join(*[f.foldername for f in self.ancestry(includeSelf=includeSelf)])
    def relpath(self, includeSelf=True):
        return os.path.join(*[f.slug for f in self.ancestry(includeSelf=includeSelf)])
    def abspath(self):
        return os.path.join(settings.MEDIA_ROOT, GALLERIA_ROOT, self.folderpath())
    def save(self, *args, **kwargs):
        me = self.abspath()
        if not os.path.isdir(me):
            os.makedirs(me)
        self.htaccess()
        Gallery.save(self, *args, **kwargs)
    @property
    def publicAncestry(self):
        """Returns True if self and all parents are public"""
        return all([f.is_public for f in self.ancestry(includeSelf=True)])

    
class AutoCollection(Gallery):
    queryfield = models.CharField(null=False, blank=False, default='date_taken', max_length=50, verbose_name=_('Field name used to query photos and galleries'))
    ordering = models.CharField(choices = (('', 'Ascending'), ('-', 'Descending')), max_length=1, default='', null=False, verbose_name=_('Ordering used to chose photos and galleries'))
    number = models.IntegerField(blank=False, null=False, default=100, verbose_name=_('Maximum number of photos to show (0 means all)'))
    galleryNumber = models.IntegerField(blank=False, null=False, default=6, verbose_name=_('Maximum number of galleries to show (0 means all) [unused]'))
    includeGalleries = models.BooleanField(default=False, verbose_name=_('Include galleries in this collection?'))

    class Meta:
        ordering = ['title']
    
    def __getquery(self, query, user=None, **filt):
        if str(self.queryfield)=='date_taken': filt['date_taken__lt']=F('date_added') # Ignores objects with invalid date_taken EXIF

        q = query.getRestricted(user, **filt).order_by(self.order_by)

        if self.number==0: n = q.count()-1
        else: n = min(self.number, q.count()-1)
        cutoff = getattr(q[n], self.queryfield)
        if self.ordering == '': ranger = str(self.queryfield) + '__lt'
        else: ranger = str(self.queryfield) + '__gt'
        filtme={}; filtme[ranger]=cutoff
        return q.filter(**filtme)

    @property
    def order_by(self):
        return self.ordering+self.queryfield

    @property
    def photo_children(self):
        return self.__getquery(Photo.objects)

    @property
    def folder_children(self):
        if self.includeGalleries:
            return self.__getquery(Folder.objects)
        return Folder.objects.none()

    @property 
    def publicAncestry(self):
        return self.is_public

    @property
    def gallery_children(self):
        return self.folder_children

    def sample(self, count=0, user=None, public=True):
        if count==0: count = self.photo_children.all().count()
        filt ={}
        if public: filt['is_public']=True; filt['parent__is_public']=True;
        return self.__getquery(Photo.objects, **filt)[:count]


#class Collection(Gallery):
#    """Arbitrary collection of photos"""
#    photo_children = models.ManyToManyField(Photo, related_name='in_collections', verbose_name=_('photos'),
#                                        null=True, blank=True)
#    gallery_children = models.ManyToManyField(Gallery, related_name='in_collections', verbose_name=_('collections'), null=True, blank=True

