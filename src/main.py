'''
Pictures demo
=============

This is a basic picture viewer, using the scatter widget.
'''

import kivy
kivy.require('1.0.6')

from glob import glob
from random import randint
from os.path import join, dirname
from kivy.app import App
from kivy.logger import Logger
from kivy.uix.scatter import Scatter
from kivy.properties import StringProperty,BooleanProperty
# FIXME this shouldn't be necessary

from kivy.clock import Clock
from kivy.core.window import Window

from kivy.animation import Animation

import argparse, hashlib, json, sys, os

from urllib2 import quote, urlopen
from urllib import urlretrieve



class APIPost(object):
    def __init__(self, domain, data):
        self.domain = domain

        self.index = data['id']
        self.parent = data['parent_id']

        self.uploader = data['author']
        self.creation = data['created_at']

        self.size = data['file_size']
        self.md5 = data['md5']

        self.tags = data['tags'].split()
        self.score = data['score']
        self.rating = data['rating']
        self.local_files= {'full':False,'sample':False, 'preview':False}
        self.files = {
            'full': (
                data['file_url'],
                data['width'],
                data['height']
            ),
            'sample': (
                data['sample_url'],
                data['sample_width'],
                data['sample_height']
            ),
            'preview': (
                data['preview_url'],
                data.get('preview_width') or data.get('actual_preview_width'),
                data.get('preview_height') or data.get('actual_preview_height')
            ),
        }

    def name(self, image_type):
        link = self.files.get(image_type)

        if not link:
            return

        return str(self.index) + '.' + link[0][link[0].rfind('.')+1:]

    def get_url(self, image_type):
        link = self.files.get(image_type)

        if not link:
            return

        if 'http://' in link[0]:
            link = link[0]
        else:
            link = "http://"+self.domain + link[0]

        return link

import threading
from functools import partial
class Downloader(threading.Thread):
    
    def __init__(self,url,dest,on_complete,on_progress):
        self.url=url
        self.dest=dest
        self.on_complete=on_complete
        self.on_progress=on_progress
        threading.Thread.__init__(self)
    
    def run(self):
        urlretrieve(self.url, self.dest, reporthook=self._progress)
        Clock.schedule_once(partial(self.on_complete,self))
        
    def _progress(self,*k):
        Clock.schedule_once(partial(self.on_progress,*k))
        

class Picture(Scatter):
    '''Picture is the class that will show the image with a white border and a
    shadow. They are nothing here because almost everything is inside the
    picture.kv. Check the rule named <Picture> inside the file, and you'll see
    how the Picture() is really constructed and used.

    The source property will be the filename to show.
    '''
        
    source = StringProperty(None)
    image_type = StringProperty(None)
    selected = BooleanProperty(None)
    full = BooleanProperty(None)
    
    def __init__(self,post,sourcepos,**kw):
        self.downloader=None
        self.post= post 
        self.download('preview')
        Scatter.__init__(self,**kw)
        self.back_animation=Animation(pos=sourcepos,scale=1.2, rotation=0.0)
        self.center_animation=Animation(pos=(0,0),scale=10.0, rotation=0.0)        
        self.next_animation=Animation(pos=(2000,sourcepos[1]),scale=0.1)
        self.prev_animation=Animation(pos=(-1000,sourcepos[1]),scale=0.1)
        self.touches=set()
        
    def do_unfocus(self):
        self.back_animation.start(self)
    
    def on_scale(self,instance,value):
        if value <= 2.0:
            self.download('preview') 
        elif value <=10.0:
            self.download('sample') 
        else:
            self.download('full') 
        
    def on_touch_down(self, touch):
        if not self.collide_point(touch.x, touch.y):
            return
        self.touches.add(touch.uid)
        if not self.selected:
            self.selected= True
        
        if touch.is_double_tap:
            self.full=True
            self.center_animation.start(self)            
            return True
        self.back_animation.stop(self)
        return Scatter.on_touch_down(self, touch)
    
    def on_touch_up(self, touch):
        try:
            self.touches.remove(touch.uid)
            if not self.touches and not self.selected: 
                self.back_animation.start(self)
        except:
            pass
        return Scatter.on_touch_up(self, touch)
    
    def on_selected(self,instance,value):
        if not value and not self.touches:
            self.back_animation.start(self)
    
    def download(self, image_type, path=None, pre=None):
        post= self.post
        if self.image_type == image_type:
            return 
        
        self.image_type=image_type
        
        
        if pre == None:
            pre= ''
        
        if path == None:
            path= ""
        else:
            if not os.path.exists(path):
                os.mkdir(path)
                
        dir= os.path.join(path, post.domain)
        if not os.path.exists(dir):
            os.mkdir(dir)
            
        dir= os.path.join(dir, image_type)
        if not os.path.exists(dir):
            os.mkdir(dir)
        
        dest = os.path.join(dir, post.name(image_type))
        
        if os.path.isfile(dest):
            
            if image_type != 'full':
                self.source = dest
                return
            
            if self.downloader is not None:
                pass
            
            if self.post.local_files[image_type]:
                Logger.warn( "Caching found of %d."%(self.post.index,))
                self.source = dest
                return           
            
            with open(dest, 'rb') as f:
                bin = f.read()
    
            if post.md5 == hashlib.md5(bin).hexdigest():
                Logger.warn( "md5 correct found of %d: %s."%(self.post.index,dest))
                self.post.local_files[image_type]=True
                self.source = dest
                return 

        if self.downloader is not None:
            pass
        url = post.get_url(image_type)
        if not url:
            Logger.warn('invalid')
            return
        Logger.warn('downloading ')
        self.downloader= Downloader(url,dest,self.download_complete, self.download_progress)
        self.downloader.start()
        
    def download_progress(self, count, blockSize, totalSize,*k):
        progress = int(count * blockSize * 100 / totalSize)
        progress = min(100, progress)
        if count * blockSize == totalSize:
            Logger.warn("Total ok!")
        Logger.warn( '%s%%' % (progress,))
    
    def download_complete(self,dl,*k):
        self.source = dl.dest
        self.downloader=None
            
class APIServer:
    
    def __init__(self,domain):
        self.domain= domain
        if not os.path.exists(self.domain):
            os.mkdir(self.domain)
        self.cache={}
    
    def get_post(self,id,data=None):
        if id in self.cache:
            return self.cache[id]
        if data is not None:
            post= self.cache[id]= APIPost(self.domain, data)
            return post
        raise Exeption("Errorus!")
    
    def get_posts(self, tags, page, limit):
        if not isinstance(tags,str):
            tags = quote(' '.join(tags))
        else:
            tags = quote(tags)
        dir= self.domain+'/post'
        
        if not os.path.exists(dir):
            os.mkdir(dir)
        
        query = '%s/index.json?tags=%s&page=%s&limit=%s' % (dir,tags, page, limit)

        if os.path.isfile(query):
            with open(query, 'rb') as f:
                data = f.read()
            try:
                return [self.get_post(x['id'],x) for x in json.loads(data)]
            except:
                pass
        
        data = urlopen("http://" + query).read()
        with open(query, 'wb') as f:
            f.write(data)
        return [self.get_post(x['id'],x) for x in json.loads(data)]

class APIResultIterator:
    
    def __init__(self,api,tags):
        self.api=api
        self.tags=tags
        self.offset=0
        self.page=1
        self.limit=0
        self.cache={}
        
    def getPrevPage(self):
        pass
    
    def getNextPage(self):
        pass
    
    def getNext(self):
        if self.offset < 0:
            self.getPrevPage()
            
        
        self.offset+=1
        
class PicturesApp(App):

    def build(self):

        # the root is created in pictures.kv
        root = self.root
        
        root.next= self.next
        root.prev= self.prev
        
        self.pictures=[]
        
        self.api= APIServer("e621.net")
        self.page= 0
    
    def next(self,*k):
        root = self.root
        self.page += 1 
        posts= iter(self.api.get_posts("pony rating:s",self.page,12))
        
        for pic in self.pictures:
            def remove(*k):
                root.remove_widget(pic)
            pic.next_animation.bind(on_complete=remove)
            pic.next_animation.start(pic)
        
        for x in range(0,4):
            for y in range(0,3):
                try:
                    post=posts.next()
                    # load the image
                    picture = Picture(post,(x*200+50,y*200+50),pos=(-1000,y*200+50), scale=0.1,  rotation=0 )
                    picture.back_animation.start(picture)
                    picture.bind( selected=self.picture_on_selected )
                    # add to the main field
                    root.add_widget(picture)
                    self.pictures.append(picture)
                except Exception, e:
                    Logger.exception('Pictures: Unable to load <%s>')
    
    def prev(self,*k):
        root = self.root
        
        if self.page <= 1:
            return
        
        self.page-=1
        posts= iter(self.api.get_posts("pony rating:s",self.page,12))
        
        for pic in self.pictures:
            def remove(*k):
                root.remove_widget(pic)
            pic.prev_animation.bind(on_complete=remove)
            pic.prev_animation.start(pic)
            
        self.pictures=[]
        
        for x in range(0,4):
            for y in range(0,3):
                try:
                    post=posts.next()
                    # load the image
                    picture = Picture(post,(x*200+50,y*200+50),pos=(2000,y*200+50), scale=0.1,  rotation=0 )
                    picture.back_animation.start(picture)
                    picture.bind( selected=self.picture_on_selected )
                    # add to the main field
                    root.add_widget(picture)
                    self.pictures.append(picture)
                except Exception, e:
                    Logger.exception('Pictures: Unable to load <%s>')
    
    def picture_on_selected(self, instance, value):
        if value:
            for pic in self.pictures:
                if pic is not instance:
                    pic.selected=False
    
    def on_pause(self):
        return True


if __name__ == '__main__':
    PicturesApp().run()

