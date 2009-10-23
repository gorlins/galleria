""" Newforms Admin configuration for Photologue

"""
from django.contrib import admin
from models import *

def make_shared(modeladmin, request, queryset):
    for obj in queryset:
        obj.is_public=2
        obj.save()
        if queryset.model is Photo:
            try:
                obj.parent.save()
            except AttributeError:
                pass
make_shared.short_description = 'Make selected public (shared)'

def make_public(modeladmin, request, queryset):
    for obj in queryset:
        obj.is_public=1
        obj.save()
        if queryset.model is Photo:
            try:
                obj.parent.save()
            except AttributeError:
                pass
make_public.short_description = 'Make selected public'

def make_private(modeladmin, request, queryset):
    for obj in queryset:
        obj.is_public=0
        obj.save()
        if queryset.model is Photo:
            try:
                obj.parent.save()
            except AttributeError:
                pass
make_private.short_description = 'Make selected private'

def publishFolderContents(folder, request, queryset):
    for folder in queryset:
        folder.is_public=2
        folder.photo_children.filter(is_public=1).update(is_public=2)
        folder.save()
publishFolderContents.short_description = "Publish folder and contents"
def unpublishFolderContents(folder, request, queryset):
    for folder in queryset:
        folder.is_public=1
        folder.photo_children.filter(is_public=2).update(is_public=1)
        folder.save()
unpublishFolderContents.short_description = "Unpublish folder and contents"
def resave(modeladmin, request, queryset):
    for obj in queryset:
        obj.save()
resave.short_description = "Resave all"

def deleteme(modeladmin, request, queryset):
    for obj in queryset:
        obj.delete()
deleteme.short_description = "Properly delete objects"

def precache(modeladmin, request, queryset):
    for obj in queryset:
        if isinstance(obj, Photo):
            obj._pre_cache()
        else:
            map(Photo._pre_cache, obj.photo_children.all())
precache.short_description = 'Precache photos'

class GalleryAdmin(admin.ModelAdmin):
    list_display = ('title', 'date_added', 'photo_count', 'is_public')
    list_filter = ['date_added', 'is_public']
    search_fields = ['title', 'description']
    date_hierarchy = 'date_added'
    prepopulated_fields = {'title_slug': ('title',)}
    #filter_horizontal = ('photos',)

class FolderAdmin(admin.ModelAdmin):
    list_display = ('foldername', 'admin_thumb', 'title', 'date_added', 'photo_count', 'is_public')
    list_filter = ['date_added', 'is_public', 'parent']
    search_fields = ['title', 'description', 'foldername']
    date_hierarchy = 'date_added'
    prepopulated_fields = {'slug': ('foldername',)}
    actions = [publishFolderContents, unpublishFolderContents]

class AutoCollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'admin_thumb', 'date_added', 'is_public')
    list_filter = ['date_added', 'is_public']
    search_fields = ['title', 'description', 'queryfield']
    date_hierarchy = 'date_added'
    prepopulated_fields = {'slug': ('title',)}


class PhotoAdmin(admin.ModelAdmin):
    #list_display = ('title', 'date_taken', 'date_added', 'is_public', 'tags', 'view_count', 'admin_thumbnail')
    list_display = ('admin_thumb', 'title', 'image', 'is_public', 'num_views', 'parent')
    list_filter = ['date_added', 'date_taken', 'is_public', 'parent']
    search_fields = ['title', 'caption']
    list_per_page = 10
    prepopulated_fields = {'slug': ('title',)}
    #prepopulated_fields = {'title_slug': ('title',)}
    #filter_horizontal = ('public_galleries',)

admin.site.add_action(deleteme)
admin.site.add_action(make_shared)
admin.site.add_action(make_public)
admin.site.add_action(make_private)
admin.site.add_action(resave)
admin.site.add_action(precache)
#admin.site.register(Gallery, GalleryAdmin)
admin.site.register(Folder, FolderAdmin)
admin.site.register(AutoCollection, AutoCollectionAdmin)
#admin.site.register(GalleryUpload)
admin.site.register(Photo, PhotoAdmin)
#admin.site.register(PhotoEffect, PhotoEffectAdmin)
#admin.site.register(PhotoSize, PhotoSizeAdmin)
#admin.site.register(Watermark, WatermarkAdmin)
