#!/usr/bin/env python3
# -*- coding: utf-8 -*-


__author__ = 'Rick'


'url handlers'


import re, time, json, logging, hashlib, base64, asyncio
import markdown2, markdown

from aiohttp import web
from coroweb import get, post

from models import User, Comment, Blog, Book, next_id

from apis import Page, APIError, APIValueError, APIResourceNotFoundError, APIPermissionError
from config import configs


COOKIE_NAME = 'deepsession'
_COOKIE_KEY = configs.session.secret

markdown2_extras=extras=[
	'code-friendly', 'break-on-newline', 'fenced-code-blocks', 'cuddled-lists', 
	'footnotes', 'header-ids', 'numbering', 'metadata', 'nofollow', 'pyshell', 'smarty-pants',
	'spoiler','target-blank-links', 'toc','tables', 'use-file-vars','wiki-tables']


def check_admin(request):
	if request.__user__ is None or not request.__user__.admin:
		raise APIPermissionError()


def get_page_index(page_str):
	p = 1
	try:
		p = int(page_str)
	except ValueError as e:
		pass
	if p < 1:
		p = 1
	return p


def text2html(text):
	lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
	return ''.join(lines)


def user2cookie(user, max_age):
	'''
	Generate cookie str by user.
	'''
	# build cookie string by: id-expires-sha1
	expires = str(int(time.time() + max_age))
	s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
	L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
	return '-'.join(L)


async def cookie2user(cookie_str):
	'''
	Parse cookie and load user if cookie is valid.
	'''
	if not cookie_str:
		return None
	try:
		L = cookie_str.split('-')
		if len(L) != 3:
			return None
		uid, expires, sha1 = L
		if int(expires) < time.time():
			return None
		user = await User.find(uid)
		if user is None:
			return None
		s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
		if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
			logging.info('invalid sha1')
			return None
		user.passwd = '******'
		return user
	except Exception as e:
		logging.exception(e)
		return None


@get('/')
async def index(request):
	blogs = await Blog.findAll(orderBy='created_at desc')
	return {
		'__template__': 'blogs.html',
		'blogs': blogs
	}


@get('/books')
async def get_books(*, page='1'):
	books = await Book.findAll(orderBy='created_at desc')
	return {
		'__template__':'books.html',
		'books': books,
	}


@get('/api/books')
async def api_books(*, page='1'):
	page_index = get_page_index(page)
	num = await Book.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, books=())
	books = await Book.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, books=books)


@post('/api/books')
async def api_create_book(request, *, name, author, image, year, introduction, content):
	check_admin(request)
	if not name or not name.strip():
	    raise APIValueError('name', 'name cannot be empty.')
	if not author or not author.strip():
		raise APIValueError('author', 'author cannot be empty.')
	if not introduction or not introduction.strip():
		raise APIValueError('introduction', 'introduction cannot be empty.')
	book = Book(name=name.strip(), author=author.strip(), image=image.strip(),
			year=year, introduction=introduction.strip(), content=content.strip())
	await book.save()
	return book


@get('/api/books/{id}')
async def api_get_book(*, id):
	book = await Book.find(id)
	return book


@post('/api/books/{id}')
async def api_update_book(id, request, *, name, author, image, year, introduction, content):
	check_admin(request)
	if not name or not name.strip():
	    raise APIValueError('name', 'name cannot be empty.')
	if not author or not author.strip():
	    raise APIValueError('author', 'author cannot be empty.')
	if not introduction or not introduction.strip():
		raise APIValueError('introduction', 'introduction cannot be empty.')
	book = await Book.find(id)
	book.name = name.strip()
	book.author = author.strip()
	book.image = image.strip()
	book.year = year
	book.introduction = introduction.strip()
	book.content = content.strip()
	await book.update()
	return book

@post('/api/books/{id}/delete')
async def api_delete_book(request, *, id):
	check_admin(request)
	book = await Book.find(id)
	await book.remove()
	return dict(id=id)


@get('/book/{id}')
async def get_book(id):
	book = await Book.find(id)
	if not book.content or not book.content.strip():
		book.html_content = ''
	else:
		book.html_content = markdown2.markdown(book.content, extras=markdown2_extras)
	book.html_introduction = markdown2.markdown(book.introduction, extras=markdown2_extras)
	return {
		'__template__': 'book.html',
		'book': book
	}


@get('/manage/books')
async def manage_books(*, page='1'):
	return {
		'__template__': 'manage_books.html',
		'page_index': get_page_index(page)
	}


@get('/manage/books/create')
async def manage_create_book():
	return {
		'__template__': 'manage_book_edit.html',
		'id': '',
		'action': '/api/books'
	}

@get('/manage/books/edit')
async def manage_edit_book(*, id):
	return {
		'__template__': 'manage_book_edit.html',
		'id': id,
		'action': '/api/books/%s' % id
	}


@get('/blog/{id}')
async def get_blog(id):
	blog = await Blog.find(id)
	comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
	for c in comments:
		c.html_content = text2html(c.content)
	blog.html_content = markdown2.markdown(blog.content, extras=[
		'code-friendly', 
		'break-on-newline',
		'fenced-code-blocks', 
		'cuddled-lists', 
		'footnotes', 
		'header-ids', 
		'numbering',
		'metadata',
		'nofollow',
		'pyshell',
		'smarty-pants',
		'spoiler',
		'target-blank-links',
		'toc',
		'tables',
		'use-file-vars',
		'wiki-tables'
	])
	'''
	blog.html_content = markdown.markdown(blog.content, output_format='html5', extensions=[
		'extra', 
		'admonition', 
		'codehilite', 
		'nl2br', 
		'toc', 
		'fenced_code', 
		'footnotes', 
		'tables', 
		'legacy_attrs', 
		'meta', 
		'sane_lists', 
		'smarty', 
		'wikilinks'
	])
	'''
	#blog.html_content = markdown.markdown(blog.content, extensions=['extra', 'codehilite'])
	return {
		'__template__': 'blog.html',
		'blog': blog,
		'comments': comments
	}


@get('/api/blogs/{id}')
async def api_get_blog(*, id):
	blog = await Blog.find(id)
	return blog


@post('/api/blogs/{id}')
async def api_update_blog(id, request, *, name, summary, content):
	check_admin(request)
	if not name or not name.strip():
		raise APIValueError('name', 'name cannot be empty')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cannot be empty')
	if not content or not content.strip():
		raise APIValueError('content', 'content cannot be empty')
	blog = await Blog.find(id)
	blog.name = name.strip()
	blog.summary = summary.strip()
	blog.content = content.strip()
	await blog.update()
	return blog


@post('/api/blogs/{id}/delete')
async def api_delete_blog(request, *, id):
	check_admin(request)
	blog = await Blog.find(id)
	await blog.remove()
	return dict(id=id)


@get('/manage/blogs/create')
async def manage_create_blog():
	return {
		'__template__': 'manage_blog_edit.html',
		'id': '',
		'action': '/api/blogs'
	}


@get('/manage/blogs/edit')
async def manage_edit_blog(*, id):
	return {
		'__template__': 'manage_blog_edit.html',
		'id': id,
		'action': '/api/blogs/%s' % id
	}


@get('/manage/')
async def manage():
	return 'redirect:/manage/comments'


@get('/manage/comments')
async def manage_comments(*, page='1'):
	return {
		'__template__': 'manage_comments.html',
		'page_index': get_page_index(page)
	}


@get('/api/comments')
async def api_comments(*, page='1'):
	page_index = get_page_index(page)
	num = await Comment.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, comments=())
	comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	logging.info('api comments p: %s, has previous: %s, has_next: %s' % (str(p), p.has_previous, p.has_next))
	return dict(page=p, comments=comments)


@post('/api/blogs/{id}/comments')
async def create_blog_comment(id, request, *, content):
	user = request.__user__
	if not user:
		raise APIPermissionError('permission sigin first')
	if not content or not content.strip():
		raise APIValueError('comment', 'comment is empty')
	blog = await Blog.find(id)
	if not blog:
		raise APIResourceNotFoundError('not exist blog id')
	comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, 
			content=content.strip())
	logging.info('handler comment: %s' % str(comment))
	await comment.save()
	return comment


@post('/api/comments/{id}/delete')
async def api_delete_comment(request, *, id):
	check_admin(request)
	comment = await Comment.find(id)
	await comment.remove() 
	return dict(id=id)


@get('/api/blogs')
async def api_blogs(*, page='1'):
	page_index = get_page_index(page)
	num = await Blog.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, blogs=())
	blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, blogs=blogs)


@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):
	check_admin(request)
	if not name or not name.strip():
		raise APIValueError('name', 'name cannot be empty.')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cannot be empty.')
	if not content or not content.strip():
		raise APIValueError('content', 'content cannot be empty.')
	blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name,
			user_image=request.__user__.image, name=name.strip(), summary=summary.strip(),
			content=content.strip())
	await blog.save()
	return blog


@get('/manage/blogs')
async def manage_blogs(*, page='1'):
	return {
		'__template__': 'manage_blogs.html',
		'page_index': get_page_index(page)
	}


@get('/manage/users')
async def manage_users(*, page='1'):
	return {
		'__template__': 'manage_users.html',
		'page_index': get_page_index(page)
	}


@get('/register')
async def register():
	return {
		'__template__': 'register.html'
	}


@get('/signin')
async def signin():
	return {
		'__template__': 'signin.html'
	}


@post('/api/authenticate')
async def authenticate(*, email, passwd):
	if not email:
		raise APIValueError('email', 'Invalid email.')
	if not passwd:
		raise APIValueError('passwd', 'Invalid password.')
	users = await User.findAll('email=?', [email])
	if len(users) == 0:
		raise APIValueError('email', 'Email not exist.')
	# check passwd
	user = users[0]
	sha1 = hashlib.sha1()
	sha1.update(user.id.encode('utf-8'))
	sha1.update(b':')
	sha1.update(passwd.encode('utf-8'))
	if user.passwd != sha1.hexdigest():
		raise APIValueError('passwd', 'Invalid password.')
	# authenticate ok, set cookie:
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r


@get('/signout')
async def signout(request):
	referer = request.headers.get('Referer')
	r = web.HTTPFound(referer or '/')
	r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
	logging.info('user signed out')
	return r


_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


@post('/api/users')
async def api_register_user(*, email, name, passwd):
	if not name or not name.strip():
		raise APIValueError('name')
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email')
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError('passwd')
	users = await User.findAll('email=?', [email])
	if len(users) > 0:
		raise APIError('register:failed', 'email', 'Email is already in use.')
	uid = next_id()
	sha1_passwd = '%s:%s' % (uid, passwd)
	user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
	await user.save()
	# make session cookie:
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r


@get('/api/users')
async def api_get_users(*, page='1'):
	page_index = get_page_index(page)
	num = await User.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, users=())
	users = await User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	for u in users:
		u.passwd = '******'
	return dict(page=p, users=users)


@get('/user/{id}')
async def get_user(id):
	user = await User.find(id)
	return dict(user=user)



