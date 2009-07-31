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

GALLERIA_ROOT = getattr(settings, 'GALLERIA_ROOT', 'galleria')
SAMPLE_SIZE = getattr(settings, 'GALLERY_SAMPLE_SIZE', 3)
PRIVATE_IPS = getattr(settings, 'GALLERIA_PRIVATE_IPS', ['none'])
def uploadFolder(photo, filename):
    return os.path.join(GALLERIA_ROOT, photo.folderpath(), filename)

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

    class Meta:
        ordering = ['date_taken']
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

    def get_next_n(self, n=4, **kwargs):
        out = []
        next = self
        for i in range(n):
            next=next.get_next(**kwargs)
            if next is None:
                break
            out.append(next)
        return out

    def get_previous_n(self, n=4, **kwargs):
        out = []
        prev = self
        for i in range(n):
            prev=prev.get_previous(**kwargs)
            if prev is None:
                break
            out.append(prev)
        out.reverse()
        return out

    def get_next(self, public=True):
        try:
            if public: return self.get_next_by_date_taken(parent=self.parent, is_public=True)
            else: return self.get_next_by_date_taken(parent=self.parent)
        except Photo.DoesNotExist:
            return None

    def get_previous(self, public=True):
        try:
            if public: return self.get_previous_by_date_taken(parent=self.parent, is_public=True)
            else: return self.get_previous_by_date_taken(parent=self.parent)
        except Photo.DoesNotExist:
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
        return ''.join(['<img src="%s"/>'%im.smallthumb.url for im in self.sample(count=3, public=False)])

    admin_thumb.short_description = _('Thumbnail')
    admin_thumb.allow_tags = True

    def get_absolute_url(self):
        return reverse('gl-gallery', args=[self.slug])

    def latest(self, limit=0, public=True):
        if limit == 0:
            limit = self.photo_count()
        if public:
            return self.public()[:limit]
        else:
            return self.photos.all()[:limit]

    def samplegallery(self, public=True):
        return self.sample(count=SAMPLE_SIZE, public=public)

    def pickSamples(self, count=0, public=True, force=False):
        self.samples = self.sample(count=count, public=public) 

    def sample(self, count=0, public=True):
        photo_set = self.photo_children.all()
        if public: photo_set = photo_set.filter(is_public=True)

        mycount = photo_set.count()

        if count > mycount or mycount==0:
            children = self.gallery_children.all()
            if public: children = children.filter(is_public=True)
            photo_set = reduce(operator.or_, [photo_set]+[g.photo_children.all() for g in children])
            if public: photo_set = photo_set.filter(is_public=True)
        if count==0: pick = photo_set.count()
        else: pick = count
        return photo_set.order_by('-num_views')[:pick]

    def photo_count(self, public=True):
        p = self.photo_children.all()
        if public: p = p.filter(is_public=True)
        return p.count()
    photo_count.short_description = _('count')
	
    def public(self):
        return self.photo_children.filter(is_public=True)
 
    def save(self, *args, **kwargs):
        if self.photo_count(public=False):
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

    def public_galleries(self):
        return self.folder_children.filter(is_public=True)
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

#class Collection(Gallery):
#    """Arbitrary collection of photos"""
#    photo_children = models.ManyToManyField(Photo, related_name='in_collections', verbose_name=_('photos'),
#                                        null=True, blank=True)
#    gallery_children = models.ManyToManyField(Gallery, related_name='in_collections', verbose_name=_('collections'), null=True, blank=True

