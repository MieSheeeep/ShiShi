"""Versioned, editable recipe document. Parsers may still submit legacy drafts."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
import re
from pydantic import BaseModel, Field, field_validator, model_validator
from backend.source_urls import canonical_url

def now(): return datetime.now(timezone.utc).isoformat()
def new_id(): return uuid4().hex

LOCAL_IMAGE = re.compile(r'/api/(?:media/[a-f0-9]{64}|demo/[a-z0-9-]+)\.(?:jpg|png|webp|gif)')

def local_images(urls):
    if len(urls)>48 or any(not LOCAL_IMAGE.fullmatch(u) for u in urls):
        raise ValueError('图片必须是食拾已保存的本地图片')
    return urls

def normalize_document(value):
    data=deepcopy(value)
    if data.get('schema_version',1) not in (1,2):
        raise ValueError('不支持的食谱版本')
    old_source=data.get('source') or ''
    if isinstance(old_source,str):
        data['source']={'url':old_source,'author':data.get('author',''),
                        'original_text':data.get('source_text',''),'original_images':data.get('source_images',[])}
    data['images']=data.get('images',data.get('source_images',[]))
    old_images=data.get('step_images',[])
    steps=[]
    for index,item in enumerate(data.get('steps',[])):
        step={'text':item,'images':old_images[index] if index<len(old_images) else []} if isinstance(item,str) else dict(item)
        step.setdefault('id',new_id());step.setdefault('images',[])
        steps.append(step)
    data['steps']=steps
    # Preserve orphaned legacy images rather than silently discard them.
    for group in old_images[len(steps):]:
        data['images']=list(dict.fromkeys(data['images']+group))
    data['ingredients']=[dict(i,id=i.get('id') or new_id()) for i in data.get('ingredients',[])]
    choices=data['tags'] if 'tags' in data else [{'id':tid} for tid in data.get('tag_ids',[])]
    data['tags']=[{'name':t,'group':'我的分类'} if isinstance(t,str) else t for t in choices]
    data['schema_version']=2
    return data

class Source(BaseModel):
    platform: str = ''
    url: str = ''
    author: str = Field(default='',max_length=500)
    original_text: str = Field(default='',max_length=50000)
    original_images: list[str] = Field(default_factory=list,max_length=48)
    imported_at: str | None = None
    @field_validator('url')
    @classmethod
    def clean_url(cls,v): return canonical_url(v) if v else ''
    @field_validator('original_images')
    @classmethod
    def clean_images(cls,v): return local_images(v)
    @model_validator(mode='after')
    def platform_from_url(self):
        self.platform='xiaohongshu' if 'xiaohongshu.com' in self.url else 'douguo' if self.url else 'manual'
        return self

class Ingredient(BaseModel):
    id: str = Field(default_factory=new_id,min_length=1,max_length=80)
    name: str = Field(min_length=1,max_length=100)
    amount: str = Field(default='未注明',max_length=100)
    kind: str = '食材'
    @field_validator('name')
    @classmethod
    def nonempty(cls,v):
        if not v.strip():raise ValueError('食材名称不能为空')
        return v.strip()

class Step(BaseModel):
    id: str = Field(default_factory=new_id,min_length=1,max_length=80)
    text: str = Field(min_length=1,max_length=10000)
    images: list[str] = Field(default_factory=list,max_length=24)
    @field_validator('images')
    @classmethod
    def clean_images(cls,v):return local_images(v)
    @field_validator('text')
    @classmethod
    def nonempty(cls,v):
        if not v.strip():raise ValueError('步骤不能为空')
        return v.strip()

class TagRef(BaseModel):
    id: str | None = None
    group: str = Field(default='我的分类',max_length=80)
    name: str = Field(default='',max_length=80)

class Recipe(BaseModel):
    schema_version: int = 2
    name: str = Field(min_length=1,max_length=200)
    source: Source = Field(default_factory=Source)
    minutes: str = ''
    servings: str = ''
    emoji: str = '🍲'
    tags: list[TagRef] = Field(default_factory=list,max_length=60)
    tag_ids: list[str] = Field(default_factory=list,max_length=60)
    notes: str = Field(default='',max_length=50000)
    images: list[str] = Field(default_factory=list,max_length=48)
    cover: str = ''
    ingredients: list[Ingredient] = Field(min_length=1,max_length=200)
    steps: list[Step] = Field(min_length=1,max_length=200)
    original_snapshot: dict | None = None
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    @model_validator(mode='before')
    @classmethod
    def legacy_input(cls,data):return normalize_document(data)
    @field_validator('images')
    @classmethod
    def clean_images(cls,v):return local_images(v)
    @field_validator('cover')
    @classmethod
    def clean_cover(cls,v):
        """封面只能使用本地图片或内置演示图，留空则前端回退到图标。"""
        if v:local_images([v])
        return v
    @model_validator(mode='after')
    def check_document(self):
        self.schema_version=2
        if not self.name.strip():raise ValueError('菜名不能为空')
        self.name=self.name.strip()
        for rows in (self.steps,self.ingredients):
            if len({row.id for row in rows})!=len(rows):raise ValueError('每个步骤和食材必须使用不同的 ID')
        local_images(list(dict.fromkeys(self.images+[u for s in self.steps for u in s.images])))
        return self

def first_picture(document):
    """取食谱的第一张图片作为默认封面：图集优先，其次步骤配图。"""
    if document.get('images'):
        return document['images'][0]
    for step in document.get('steps', []):
        if step.get('images'):
            return step['images'][0]
    return ''

def snapshot(document,kind):
    return {'kind':kind,'captured_at':now(),'recipe':{k:deepcopy(v) for k,v in document.items() if k not in ('original_snapshot','id','updated_at','created_at','tag_ids')}}

def draft_v2(raw):
    """Do not require complete fields until the user confirms a draft."""
    data=normalize_document(raw)
    source=data['source']
    source['platform']='xiaohongshu' if 'xiaohongshu.com' in source.get('url','') else 'douguo'
    source['imported_at']=now()
    data['created_at']=data['updated_at']=now()
    data['original_snapshot']=snapshot(data,'imported')
    data['cover']=data.get('cover') or first_picture(data)
    for key in ('author','source_text','source_images','step_images'):data.pop(key,None)
    return data
