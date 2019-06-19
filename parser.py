#!/usr/bin/env python3

PAPERPILE_SHARE = "https://paperpile.com/shared/GzVbWX"

from bs4 import BeautifulSoup
import requests
import json
from pprint import pprint
import os
import shutil
import git
from pathlib import Path
from ruamel.yaml import YAML
import re
import mechanicalsoup
import textwrap
import datetime

import requests
import logging

import codecs
codecs.register(lambda name: codecs.lookup('utf-8') if name == 'cp65001' else None)

logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True


browser = mechanicalsoup.StatefulBrowser(
    soup_config={'features': 'lxml'}
                                         )
browser.set_verbose(2)


# https://stackoverflow.com/a/41920796
def get_git_root(git_repo):

             
        return Path(git_repo.working_dir)

GIT_REPO = git.Repo(os.getcwd(), search_parent_directories=True)   
GIT_ROOT = get_git_root(GIT_REPO)

bibdir = GIT_ROOT / '_bibitem'
shutil.rmtree(bibdir , ignore_errors=True)

catdir = GIT_ROOT / '_themes'
shutil.rmtree(catdir, ignore_errors=True)
DUPES = "_duplicates.txt"
NO_THEME = "_notheme.txt"

with open(DUPES, "w") as dupefile:
	dupefile.write("Potential problems found:\n")
with open(NO_THEME, "w") as dupefile:
	dupefile.write("Items without theme:\n")	
try:
	os.mkdir(bibdir)
	os.mkdir(catdir)
except:
	pass
	
category_include = GIT_ROOT/'_includes'/'category.html'
broad_category_include = GIT_ROOT/'_includes'/'broadcategory.html'
shutil.rmtree(category_include, ignore_errors=True)

yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.default_flow_style = False


occuranceCount={}


def parsePage(items, browser, occuranceCount):
	soup = browser.get_current_page()
	foldername = soup.select(".pp-subfolder-self")[0].get_text()


	for div in soup.find_all(class_="pp-pub-item"):
		initialdata = re.sub(r"<[^>]+>", "", div.find(ppdata=True)['ppdata'])

		jsondata = json.loads(initialdata)

		
		catpage = re.sub(r"(https://paperpile.com/shared/\w+)/[0-9]+$", r"\1", browser.get_url())
		#print(catpage, browser.get_url())
		jsondata['category_page'] = [catpage]



		if "keywords" in jsondata:
			jsondata['keywords'] = [ x.title().strip() for x in re.split(r'[;,] *', jsondata['keywords']) if x.title().strip() ]
		else:
			jsondata['keywords'] = ['No Keywords']
		# pprint(jsondata)
		if "url" in jsondata:
			jsondata['docurls'] = jsondata['url']
			del jsondata['url']

		jsondata['jsonauthors'] = jsondata['author']
		authors = []
		citationauthor = []
		for j, author in enumerate(jsondata['author']):			
			
			if "last" in author and "first" in author:
				authors.append("{}, {}".format(author['last'], author['first']))
				initials = ""
				for i, initial in enumerate(author['initials']):
					if initial != " ":
						initials += "{}.".format(initial)
						if i < len(author['initials'])-1:
							initials += " "
				citationauthor.append("{}, {}".format(author['last'], initials))
			elif "last" in author:
				authors.append("{}".format(author['last']))
				citationauthor.append("{}".format(author['last']))
			elif "collective" in author:
				authors.append(re.sub(r' +', '_', "{}".format(author['collective'])))
				citationauthor.append(author['collective'])
			else:
				raise ValueError(author)
		authorout = authors
		if len(authorout) > 2:
			authorout = authors[:2]+['etal']
		if authors == []:
			authorout.append(jsondata['title'])

		citationauthorstring = ""
		for i, a in enumerate(citationauthor):
			if i < len(citationauthor) -2:
				citationauthorstring += "{}, ".format(a)
			elif i == len(citationauthor)-2:
				citationauthorstring += "{}, & ".format(a)
			else:
				citationauthorstring += "{}".format(a)

		jsondata['citationauthor'] = citationauthorstring
		# authorstring= '-'.join([ "{}".format(author['last']) for author in jsondata['author']] )
		authorstring = textwrap.shorten(re.sub(r'[^A-Za-z0-9-,;+]+', '-', '+'.join(authorout)), width=50, placeholder="+etal")
		jsondata['author'] = '; '.join(authors)

		if "published" in jsondata:
			year = jsondata['published']['year']
		else:
			jsondata['published'] = {}
			jsondata['published']['year'] = "n.d."
			year = "n.d."

		occuranceKey = "{}-{}".format('-'.join(authorout).upper(), jsondata['title'].upper())
		if occuranceKey in occuranceCount:
			occuranceCount[occuranceKey] += 1
		else:
			occuranceCount[occuranceKey] = 1
		jsondata['occuranceKey'] = occuranceKey
		key = "{}-{}-{}".format(year, '-'.join(authorout), textwrap.shorten(jsondata['title'], width=50, placeholder=""))
		jsondata['sortorder'] = "{}-{}-{}".format(' '.join(authors), year, jsondata['title'])

		if key in items:
			jsondata['category_page'] = jsondata['category_page'] + items[key]['category_page']			
		items[key] = jsondata




def nextPage(items, browser, occuranceCount):
	parsePage(items, browser, occuranceCount)
	try:
		nextbutton =browser.find_link(id="next-button")	
		pprint(nextbutton)
		browser.follow_link(nextbutton)

		nextPage(items, browser, occuranceCount)
	except mechanicalsoup.utils.LinkNotFoundError:
		print("Done with links")


def writePage(key, data, occuranceCount):
	key = re.sub(r"[^A-Za-z0-9-.]+","+", key)
	with codecs.open(bibdir/"{}.md".format(key) ,'w', "utf-8") as outputbib:
				data['layout']='bibitem'
				outputbib.write("---\n")
				yaml.dump(data, outputbib)
				outputbib.write("---\n")
	if occuranceCount[data['occuranceKey']] != len(data['category_page']):
		with open(DUPES, "a+") as dupes:
			dupes.write("{}\tOccurance:{}\tCategories:{}\n".format(key, occuranceCount[data['occuranceKey']], len(data['category_page'])))
	if len(data['category_page']) != len(set(data['category_page'])):
		catdupe = []
		for cat in data['category_page']:
			if cat in catdupe:
				with open(DUPES, "a+") as dupes:
					dupes.write("{}\tRepeated in category: {}\n".format(key, cat))
			catdupe.append(cat)
	if len(data['category_page']) == 1 and PAPERPILE_SHARE in data['category_page'][0] :
		with open(NO_THEME, "a+") as notheme:
			notheme.write("{}\n".format(key))


class Folder:

	foldername = ""
	folderurl = ""
	subfolders = []

	def __init__(self, foldername="?", folderurl="?"):
		self.foldername = foldername
		self.folderurl = folderurl

def clean(string):
	return re.sub("[^A-Za-z0-9-]+", "+", string)

def findSubfolder(level, items, folder_names, browser, occuranceCount):
	soup = browser.get_current_page()
	current_name = soup.select(".pp-subfolder-self")[0].get_text()
	nextPage(items, browser, occuranceCount)
	current_url = browser.get_url()

	catpage = re.sub(r"(https://paperpile.com/shared/\w+)/[0-9]+$", r"\1", browser.get_url())
	

	print("*", current_name, catpage)
	folder_names[catpage] = current_name

	#this_folder = Folder(current_name, current_url)

	subfolders = {}
	for folder in soup.select("li.pp-subfolder a"):
		
		subfolder_url=browser.absolute_url(folder['href'])
		subfolder_name = folder.get_text()
		
		folder_names[subfolder_url] = subfolder_name
		subfolders[subfolder_url] = {}

		browser.open(subfolder_url)
		
		subfolders[subfolder_url] = findSubfolder(level+1, items, folder_names, browser, occuranceCount)
		print("\t", subfolder_url, subfolder_name)
	
	
	#this_folder.subfolders = subfolders
	return subfolders
	



	
# identifier is yearauthortitle
items = {}

browser.open(PAPERPILE_SHARE)

folder_names = {}

folder_tree = findSubfolder(0, items, folder_names, browser, occuranceCount)

#pprint(occuranceCount)
with codecs.open(category_include, "w", "utf-8") as cat:
		cat.write("")
with codecs.open(broad_category_include, "w", "utf-8") as cat:
		cat.write("")

def treeWalk(level, tree, folder_names, parent_url, parent_filename, parent_name):
	with codecs.open(category_include, "a+", "utf-8") as cat:
		cat.write("<ul>\n")

	if level == 0:
		with codecs.open(broad_category_include, "a+", "utf-8") as cat:
			cat.write("<ul>\n")
		for folder in tree:
			with codecs.open(broad_category_include, "a+", "utf-8") as cat:
				cat.write((level+1)*"\t")
				category_url = "{}-{}".format(level, clean(folder_names[folder]))
				cat.write("""<li><a href="{{{{site.baseurl}}}}/themes/{}">{}</a></li>		          
	""".format(category_url, folder_names[folder] ))


	for folder in tree:
		with codecs.open(category_include, "a+", "utf-8") as cat:
			cat.write((level+1)*"\t")
			category_url = "{}-{}".format(level, clean(folder_names[folder]))
			cat.write("""<li><a href="{{{{site.baseurl}}}}/themes/{}">{}</a></li>		          
""".format(category_url, folder_names[folder] ))
		
		yaml = YAML()

		with codecs.open(catdir/"{}.md".format(category_url), "w", "utf-8") as category_file:
			category_file.write("---\n")
			catpage = {'title': folder_names[folder],
			 		   'layout': 'category',
			 		   'category_page': folder,
			 		   'parent_name': parent_name,
			 		   'parent_url': parent_url,
			 		   'permalink': '/themes/{}'.format(category_url),
			 		   'child_theme': []
					  }

			yaml.dump(catpage, category_file)
			category_file.write("---\n")
		if tree[folder]:
			treeWalk(level+1, tree[folder], folder_names, "/themes/"+category_url,category_url, folder_names[folder])

		if parent_filename:
			
			with codecs.open(catdir/"{}.md".format(parent_filename), "r", "utf-8") as yamlin:
				emptybit, header, emptybit2 = yamlin.read().split("---")
				yaml_data = yaml.load(header)
				yaml_data['child_theme'].append({'name': folder_names[folder], 'url':"/themes/"+category_url})
			with codecs.open(catdir/"{}.md".format(parent_filename), "w", "utf-8") as yamlout:
				yamlout.write("---\n")
				yaml.dump(yaml_data, yamlout)
				yamlout.write("---\n")				           
				              

	with codecs.open(category_include, "a+", "utf-8") as cat:
		cat.write("</ul>")

treeWalk(0, folder_tree, folder_names, '/references+by+theme/', None, '')

print("***")

pprint(folder_names)
pprint(folder_tree)

#nextPage(items, browser)		

for item in items:
	curitem = items[item]
	# if "Subjectivity" in curitem['title']:
	# 	pprint(curitem)
	writePage(item, curitem, occuranceCount)




