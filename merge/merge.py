#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse, sys, os, subprocess,re
print("merge.py")
parser = argparse.ArgumentParser(prog='merge')
parser.add_argument('-bss', action='store_true', help='Add bss-workspace-shared as root folder')
parser.add_argument('-rewrite', action='store_true', help='Only rewrite index of repository')
parser.add_argument('-merge', action='store_true', help='Only merge repository')
parser.add_argument('repo', nargs='+', help='Source repository. Use "repo"+prefix to add prefix directory using filter-branch.')
parser.add_argument('output', nargs=1, help='Target repository (will be created)')
arguments = parser.parse_args(sys.argv[1:])

def error(reason):
  print(reason)
  sys.exit(1)

def getBranches(repo):
  brs = subprocess.check_output(["git", "branch", "-a"],cwd=repo).decode("utf-8").split('\n')
  brs = [s[2:].strip() for s in brs]
  return brs

def getTags(repo):
  brs = subprocess.check_output(["git", "tag"],cwd=repo).decode("utf-8").split('\n')
  brs = [s.strip() for s in brs]
  return brs

def getScriptPath():
    return os.path.dirname(os.path.realpath(sys.argv[0]))

def getFileContent(name):
  lista=[]
  fullName = os.path.join(getScriptPath(), name)
  print("*** Checking "+fullName)
  if os.path.exists(fullName):
    with open(fullName) as fp:
        print("*** Reading "+fullName)
        for line in fp:
          lista.append(line.strip())
  else:
    print("*** Cannot read "+fullName)
  return lista

# Sprawdzanie formatu podanych repozytoriów czy są one adresami git
print("*** Processing parameters...")
repos=[]
for repoSpec in arguments.repo:
  splitted = repoSpec.split('+')
  expression = re.compile('((git|ssh|http(s)?)|(git@[\w\.]+))(:(//)?)([\w\.@\:/\-~]+)(\.git)(/)?')
  if not expression.match(splitted[0]):
    error("Not a git repo: " + splitted[0])
  repos.append((splitted[0],"".join(splitted[1:]).replace("-", "\\-")))

prefixesOfBranch = getFileContent("prefixes")
print("*** prefixesOfBranch: "+ ','.join(prefixesOfBranch))
skipBranch = getFileContent("skipbranch")
print("*** skipBranch: "+ ','.join(skipBranch))
skipTag = getFileContent("skiptag")
print("*** skipTag: "+ ','.join(skipTag))

# klonowanie podanych repozytoriów oraz zapamiętanie ich scieżek
print("*** Cloning repositories...")
repospath=[]
for (repo,prefix) in repos:
  name = os.path.basename(repo)[:-4]
  if not arguments.merge:
    subprocess.check_call(["git","clone",repo])
  absPath = os.path.abspath(name)
  repospath.append((absPath,prefix))



print("*** Rewriting repositories...")
branches=[]
# ściągnięcie lokalnie wszystkich repozytoriów
bashCommand="for branch in `git branch -a | grep remotes | grep -v HEAD | grep -v master`; do     git branch --track ${branch#*/*/} $branch; done"
# usunięcie polączenia ze zdalnym repozytorium(na wszelki wypadek aby nie było mozliwośći aby coś poszło do zdalnego repo)
bashRemoteRm="git remote rm origin"
if not arguments.merge:
  for (repo, prefix) in repospath:
    print("*** Cloning and rewite repository " + repo)
    subprocess.check_call(bashCommand,cwd=repo,stderr=subprocess.STDOUT,shell=True)
    subprocess.check_call(bashRemoteRm,cwd=repo,stderr=subprocess.STDOUT,shell=True)
    for tag in getTags(repo):
      if (tag and tag not in skipTag and tag.startswith("7.")):
        subprocess.check_call(["git","tag", "v"+tag, tag],cwd=repo,stderr=subprocess.STDOUT)
        subprocess.check_call(["git","tag","-d",tag],cwd=repo, stderr=subprocess.STDOUT)
    subprocess.check_call(["git", "checkout", getBranches(repo)[0]],cwd=repo, stderr=subprocess.STDOUT)
    # przepisanie hitstori indeksów repozytoriów aby wyglądało że zawsze znajdował sie w folderze prefix
    bashIndexRewrite="""git filter-branch --index-filter \
      'git ls-files -s | sed "s-\\\t\\\"*-&"""+prefix+"""/-" |
      GIT_INDEX_FILE=$GIT_INDEX_FILE.new \
      git update-index --index-info &&
      mv "$GIT_INDEX_FILE.new" "$GIT_INDEX_FILE" || true
      ' --tag-name-filter cat -f -- --all"""
    subprocess.check_call(bashIndexRewrite,cwd=repo,stderr=subprocess.STDOUT,shell=True)
    # przemianowanie branchy - usunięcie zbędnych prefiksów
    if prefixesOfBranch:
      branches = getBranches(repo)
      for bran in branches:
        for prefix in prefixesOfBranch:
            if bran.startswith(prefix):
              newbrand=bran[len(prefix):]
              subprocess.check_call(["git","branch","-m",bran,newbrand],cwd=repo, stderr=subprocess.STDOUT)


if arguments.rewrite:
  print("*** Rewriting index completed")
  sys.exit(0)






# jezeli podało się z opcja -bss dołącza się bss-workspace(chodzi głównie o bss-workspace-sherd)
if arguments.bss:
  print("*** Adding bss-workspace")
  name = os.path.basename("git@r7.telecom.comarch:bss/bss-workspace.git")[:-4]
  if not os.path.exists(name):
    subprocess.check_call(["git","clone","git@r7.telecom.comarch:bss/bss-workspace.git"], stderr=subprocess.STDOUT)
    absPath = os.path.abspath(name)
    subprocess.check_call(bashCommand,cwd=absPath,stderr=subprocess.STDOUT,shell=True)
    subprocess.check_call(bashRemoteRm,cwd=absPath,stderr=subprocess.STDOUT,shell=True)
  repospath.insert(0,(absPath,""))

# sprawdzam czy folder docelowy już istnieje
target = arguments.output[0]
if os.path.exists(target):
  error("File already exists: " + target)

# tworzymy puste repo
print("*** Creating empty git repo in " + target)
os.makedirs(target)
os.chdir(target)
subprocess.check_call(["git", "init"],stderr=subprocess.STDOUT)

# tworzenie słownika który jako klucz ma nazwe brancha a wartośc lista repozytoriów które mają ten branch
print("*** Looking for branches in repos")
branchesInRepo={}
for (repo, prefix) in repospath:
  name = os.path.basename(repo)
  subprocess.check_call(["git", "remote", "add","-f", name, repo],stderr=subprocess.STDOUT)
  branches = getBranches(repo)
  print("*** Repo "+ repo+" branches: "+','.join(branches))
  for branch in branches:
    if branch and branch not in skipBranch and not branch.startswith("remote"):
      print("*** adding "+ repo+" for branch: "+branch)
      if branch in branchesInRepo:
        branchesInRepo[branch].append(repo)
      else:
        branchesInRepo[branch]=[repo]
    else:
      print("*** skipping "+ repo+" for branch: "+branch)
  subprocess.check_call(["git", "remote", "remove", name],stderr=subprocess.STDOUT)




# dla każdego brancha robimy mergowanie ze wszystkich repozytoriów
print("*** Branch merging from all repos")
for branch,repos in branchesInRepo.items():
  print("*** Merge branch "+branch+" from repos")
  name = os.path.basename(repos[0])
  print("*** "+name)
  subprocess.check_call(["git", "remote", "add","-f", name, repos[0]], stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "fetch", "-n",name],stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "checkout", branch],stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "branch", "--set-upstream",branch,name+"/"+branch],stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "merge", "--no-edit","--no-stat",name+"/"+branch],stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "remote", "remove", name],stderr=subprocess.STDOUT)
  for repo in repos[1:]:
    name = os.path.basename(repo)
    print("*** "+name)
    subprocess.check_call(["git", "remote", "add","-f", name, repo],stderr=subprocess.STDOUT)
    subprocess.check_call(["git", "fetch", "-n",name],stderr=subprocess.STDOUT)
    subprocess.check_call(["git", "branch", "--set-upstream",branch,name+"/"+branch],stderr=subprocess.STDOUT)
    subprocess.check_call(["git", "merge", "--no-edit","--no-stat",name+"/"+branch],stderr=subprocess.STDOUT)
    subprocess.check_call(["git", "remote", "remove", name],stderr=subprocess.STDOUT)

branches = getBranches(os.getcwd())


# zmiana tymczasowo nazw branch w razie jak by tagi miały takie same nazwy jak branche
print("*** Preparing to merge tags")
for branch in branches:
  if branch:
    subprocess.check_call(["git", "branch", "-m",branch,"tmp_"+branch],stderr=subprocess.STDOUT)


# tak samo jak z branchami tylko słownik tagów i repozytoriów które je mają
print("*** Merge tags from all repos (1)")
TagsInRepo={}
for (repo, prefix) in repospath:
  name = os.path.basename(repo)
  subprocess.check_call(["git", "remote", "add","--tags", name, repo],stderr=subprocess.STDOUT)

  for tag in getTags(repo):
    if (tag and tag not in skipTag):
      if tag in TagsInRepo:
        TagsInRepo[tag].append(repo)
      else:
        TagsInRepo[tag]=[repo]
  subprocess.check_call(["git", "remote", "remove", name],stderr=subprocess.STDOUT)

# tworzymy tymczasowy branch, nastepnie mergujemy tag ze wszystkich repozytoriów
print("*** Merge tags from all repos (2)")
merged=[]
for tag,repos in TagsInRepo.items():
  name = os.path.basename(repos[0])
  subprocess.check_call(["git", "remote", "add","-f", name, repos[0]],stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "fetch","-t",name],stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "checkout","-b",tag,"tags/"+tag],stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "merge", "--no-edit","--no-stat","tags/"+tag],stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "remote", "remove", name],stderr=subprocess.STDOUT)
  for repo in repos[1:]:
    name = os.path.basename(repo)
    subprocess.check_call(["git", "remote", "add","-f", name, repo],stderr=subprocess.STDOUT)
    subprocess.check_call(["git", "fetch","-t",name],stderr=subprocess.STDOUT)
    subprocess.check_call(["git", "merge", "--no-edit","--no-stat","tags/"+tag],stderr=subprocess.STDOUT)
    subprocess.check_call(["git", "remote", "remove", name],stderr=subprocess.STDOUT)

  merged.append(tag)

# ze stworzonego brancha ze zmergowanymi tagam tworzymy tagi i usuwamy stworzone branche
print("*** Merge tags from all repos (3)")
for tag in merged:
  subprocess.check_call(["git", "checkout",tag],stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "tag", "-a","-f", tag,"-m","Merged tag "+tag],stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "checkout","tmp_master"],stderr=subprocess.STDOUT)
  subprocess.check_call(["git", "branch", "-D", tag],stderr=subprocess.STDOUT)
  # zmiana nazwy tagów które pokrywaja sie z nazwami branchy
  if tag in branches:
    subprocess.check_call(["git","tag", "tag-"+tag, tag],stderr=subprocess.STDOUT)
    subprocess.check_call(["git","tag","-d",tag],stderr=subprocess.STDOUT)

# przywrócenie nazwy branchy do ich oryginalnej nazwy
print("*** Merge tags from all repos (4)")
for branch in getBranches(os.getcwd()):
  if branch:
    if branch.startswith("tmp_"):
      subprocess.check_call(["git", "branch", "-m",branch,branch[4:]], stderr=subprocess.STDOUT)

print("*** DONE")
