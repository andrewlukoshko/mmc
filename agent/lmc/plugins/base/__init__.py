# -*- coding: utf-8; -*-
#
# (c) 2004-2007 Linbox / Free&ALter Soft, http://linbox.com
#
# $Id$
#
# This file is part of LMC.
#
# LMC is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LMC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with LMC; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from lmc.support.errorObj import errorMessage
from lmc.support.lmcException import lmcException
from lmc.support import lmctools
from lmc.support.lmctools import cSort
from lmc.support.config import *
from time import time


from lmc.support.lmctools import shProcessProtocol
from lmc.support.lmctools import generateBackgroundProcess
from lmc.support.lmctools import cleanFilter

import ldap
import ldap.schema
import ldap.modlist
import ldif
import crypt
import random
import re
import os
from lmc.support import lmctools
import ConfigParser
import copy
import tempfile
from sets import Set
import logging
import shutil
import xmlrpclib

from time import mktime, strptime, strftime, localtime

# global definition for ldapUserGroupControl
INI = "/etc/lmc/plugins/base.ini"
ldapHost=""
baseDN = ""
baseGroupsDN = ""

modList= None

VERSION = "1.1.4"
APIVERSION = "4:1:0"
REVISION = int("$Rev$".split(':')[1].strip(' $'))

def getVersion(): return VERSION
def getApiVersion(): return APIVERSION
def getRevision(): return REVISION

def listEvent():
    return lmctools.ProcessScheduler().listEvent()

def listProcess():
    ret = []
    psdict = lmctools.ProcessScheduler().listProcess()

    for i in psdict.keys():
        assoc = []
        if time() - psdict[i].time > 60:
            # Process do not respond for 60 secondes or exited for 60 seconds... remove it
            # FIXME: This should not be done here but in an internal loop of
            # ProcessScheduler()
            del psdict[i]
        else:
            assoc.append(psdict[i].desc)
            assoc.append(psdict[i].progress)
            assoc.append(psdict[i].status)
            #assoc.append(psdict[i].out)
            ret.append(assoc)

    return ret

def activate():
    """
     this function define if the module "base" can be activated.
     @return: return True if this module can be activate
     @rtype: boolean
    """
    logger = logging.getLogger()
    try:
        ldapObj = ldapUserGroupControl()
        ret = True
    except ldap.INVALID_CREDENTIALS:
        logger.error("Can't bind to LDAP: invalid credentials.")
        return False

    # Test if the LMC LDAP schema is available in the directory
    try:
         schema =  ldapObj.getSchema("lmcUserObject")
         if len(schema) <= 0:
             logger.error("LMC schema seems not be include in LDAP directory");
             ret = False
    except:
        logger.exception("invalid schema")
        ret = False

    if ret:
        # Create required OUs
        ous = [ ldapObj.baseUsersDN, ldapObj.baseComputersDN, ldapObj.baseGroupsDN, ldapObj.gpoDN ]
        for ou in ous:
            head, path = ou.split(",", 1)
            ouName = head.split("=")[1]
            try:
                ldapObj.addOu(ouName, path)
                logger.info("Created OU " + ou)
            except ldap.ALREADY_EXISTS:
                pass
    return ret

def getModList():
    """
     define all modules avaible in lmc-agent
     @rtype: list
     @return: list with all modules loaded
    """
    global modList
    return modList

def setModList(param):
    """
     set a module liste
     @param param: module list to set
     @type param: list
    """
    global modList
    modList = param

def changeAclAttributes(uid,acl):
    ldapObj = ldapUserGroupControl()
    ldapObj.changeUserAttributes(uid,acl)
    return 0

def setPrefs(uid,pref):
    ldapObj = ldapUserGroupControl()
    ldapObj.changeUserAttributes(uid,'lmcPrefs',pref)
    return 0

def getPrefs(uid):
    ldapObj = ldapUserGroupControl()
    try:
        return ldapObj.getDetailedUser(uid)['lmcPrefs'][0]
    except:
        return ''

def changeGroupDescription(cn,desc):
    ldapObj = ldapUserGroupControl()
    ldapObj.changeGroupAttributes(cn,'description',desc)
    return 0

def getUsersLdap(searchFilter = ""):
    ldapObj = ldapUserGroupControl()
    searchFilter = cleanFilter(searchFilter)
    return ldapObj.searchUser(searchFilter)

def searchUserAdvanced(searchFilter = ""):
    """
    Used by the LMC web interface to get a user list
    """
    ldapObj = ldapUserGroupControl()
    searchFilter = cleanFilter(searchFilter)
    if searchFilter:
        searchFilter = "(|(uid=%s)(givenName=%s)(sn=%s)(telephoneNumber=%s)(mail=%s))" % (searchFilter, searchFilter, searchFilter, searchFilter, searchFilter)
    return ldapObj.searchUserAdvance(searchFilter)

def getGroupsLdap(searchFilter= ""):
    ldapObj = ldapUserGroupControl()
    searchFilter=cleanFilter(searchFilter);
    return ldapObj.searchGroup(searchFilter)

def getDefaultUserGroup():
    ldapObj = ldapUserGroupControl()
    return ldapObj.defaultUserGroup;

def getUserDefaultPrimaryGroup():
    return ldapUserGroupControl().defaultUserGroup

def getUserPrimaryGroup(uid):    
    return ldapUserGroupControl().getUserPrimaryGroup(uid)

def getUserSecondaryGroups(uid):
    return ldapUserGroupControl().getUserSecondaryGroups(uid)

def createGroup(groupName):
    ldapObj = ldapUserGroupControl()
    return ldapObj.addGroup(groupName)

def existGroup(groupName):
    return ldapUserGroupControl().existGroup(groupName)

# create a user
def createUser(login, passwd, firstname, surname, homedir, primaryGroup = None):
    ldapObj = ldapUserGroupControl()
    return ldapObj.addUser(login, passwd, firstname, surname, homedir, primaryGroup)

def addUserToGroup(cngroup,uiduser):
    ldapObj = ldapUserGroupControl()
    return ldapObj.addUserToGroup(cngroup,uiduser)

def delUserFromGroup(cngroup,uiduser):
    ldapObj = ldapUserGroupControl()
    return ldapObj.delUserFromGroup(cngroup,uiduser)

def delUserFromAllGroups(uid):
    ldapObj = ldapUserGroupControl()
    return ldapObj.delUserFromAllGroups(uid)

def changeUserPrimaryGroup(uid, groupName):
    return ldapUserGroupControl().changeUserPrimaryGroup(uid, groupName)

def delUser(uiduser, home):
    ldapObj = ldapUserGroupControl()
    return ldapObj.delUser(uiduser, home)

def delGroup(cngroup):
    ldapObj = ldapUserGroupControl()
    return ldapObj.delGroup(cngroup)

# return a list of member
# return an array
def getMembers(cngroup):
    ldapObj = ldapUserGroupControl()
    return ldapObj.getMembers(cngroup)

# change password for account and
# for sambaAccount via smbpasswd
def changeUserPasswd(uiduser,passwd):
    ldapObj = ldapUserGroupControl()
    return ldapObj.changeUserPasswd(uiduser,passwd)

# return all users of a specific group
def getUserGroups(pattern):
    ldapObj = ldapUserGroupControl()
    return ldapObj.getUserGroups(pattern)

# backup fonction
def backupUser(user,media,login,configFile = "/etc/lmc/plugins/base.ini"):
    import ConfigParser
    config = ConfigParser.ConfigParser()
    config.read(configFile)

    path = config.get("backup-tools", "path")
    destpath = config.get("backup-tools", "destpath")
    cmd = path+"/"+"backup.sh"

    ldapObj = ldapUserGroupControl()
    homedir=ldapObj.getDetailedUser(user)['homeDirectory'][0]

    lmctools.shlaunchBackground(cmd+" "+user+" "+homedir+" "+destpath+" "+login+" "+media+" "+path,"backup user "+user,lmctools.progressBackup)

    return 0

#return entire ldap info on uid user
def getDetailedUser(uid):
    ldapObj = ldapUserGroupControl()
    return ldapObj.getDetailedUser(uid)

def getDetailedGroup(cn):
    ldapObj = ldapUserGroupControl()
    return ldapObj.getDetailedGroup(cn)

def getUserAttribute(uid,attr):
    return getUserAttributes(uid,attr)[0]

def getUserAcl(uid):
    if (uid=="root"):
        return "";
    ldapObj = ldapUserGroupControl()
    allInfo = ldapObj.getDetailedUser(uid)
    try:
        return allInfo['lmcACL'][0]
    except:
        #test if contain lmcUserObject
        if (not 'lmcUserObject' in allInfo['objectClass']):
            allInfo['objectClass'].append('lmcUserObject')
            ldapObj.changeUserAttributes(uid,"objectClass",allInfo['objectClass'])
        return ""

def setUserAcl(uid,aclString):
    ldapObj = ldapUserGroupControl()
    ldapObj.changeUserAttributes(uid,"lmcACL",aclString)
    return 0


def getUserAttributes(uid,attr):
    ldapObj = ldapUserGroupControl()
    arr = ldapObj.getDetailedUser(uid)
    return arr[attr]


def existUser(uid):
    #if no uid precise
    if uid=='':
        return False
    ldapObj = ldapUserGroupControl()
    return ldapObj.existUser(uid)

#change main UserAttributes
def changeUserMainAttributes(uid,newuid,name,surname):
    ldapObj = ldapUserGroupControl()

    gecos=name+" "+surname
    gecos=str(delete_diacritics(gecos.encode("utf-8")))
    name=str(name.encode("utf-8"))
    surname=str(surname.encode("utf-8"))

    if surname: ldapObj.changeUserAttributes(uid,"sn",surname)
    if name: ldapObj.changeUserAttributes(uid,"givenName",name)
    ldapObj.changeUserAttributes(uid,"gecos",gecos)
    if newuid != uid:
        ldapObj.changeUserAttributes(uid,"cn",uid)
        ldapObj.changeUserAttributes(uid,"uid",newuid)
    return 0

def changeUserAttributes(uid,attr,attrval):
    ldapObj = ldapUserGroupControl()
    ldapObj.changeUserAttributes(uid,attr,attrval)

def maxUID():
    ldapObj = ldapUserGroupControl()
    return ldapObj.maxUID()

def maxGID():
    ldapObj = ldapUserGroupControl()
    return ldapObj.maxGID()

def moveHome(uid,home):
    ldapObj = ldapUserGroupControl()
    return ldapObj.moveHome(uid,home)


def addOu(ouname, ldappath):
    """
    add Organizational Unit
     - ouname: Name of new Organizational Unit
     - ldappath : ldap path
        ex: uid=foo, ou=bar, dc=linbox, dc=com
    """
    ldapObj = ldapUserGroupControl()
    ldapObj.addOu(ouname,ldappath)

def enableUser(login):
    ldapObj = ldapUserGroupControl()
    return ldapObj.enableUser(login)

def disableUser(login):
    ldapObj = ldapUserGroupControl()
    return ldapObj.disableUser(login)

def isEnabled(login):
    ldapObj = ldapUserGroupControl()
    return ldapObj.isEnabled(login)

def isLocked(login):
    ldapObj = ldapUserGroupControl()
    return ldapObj.isLocked(login)

def getAllGroupsFromUser(uid):
    ldapObj = ldapUserGroupControl()
    return ldapObj.getAllGroupsFromUser(uid)


###log view accessor
def getLdapLog(filter = ''):
    return LogView().getLog(filter)

_reptable = {}
def _fill_reptable():
    """
     this function create array to remove accent
     not call, execute on startup
    """
    _corresp = [
        (u"A",  [0x00C0,0x00C1,0x00C2,0x00C3,0x00C4,0x00C5,0x0100,0x0102,0x0104]),
        (u"AE", [0x00C6]),
        (u"a",  [0x00E0,0x00E1,0x00E2,0x00E3,0x00E4,0x00E5,0x0101,0x0103,0x0105]),
        (u"ae", [0x00E6]),
        (u"C",  [0x00C7,0x0106,0x0108,0x010A,0x010C]),
        (u"c",  [0x00E7,0x0107,0x0109,0x010B,0x010D]),
        (u"D",  [0x00D0,0x010E,0x0110]),
        (u"d",  [0x00F0,0x010F,0x0111]),
        (u"E",  [0x00C8,0x00C9,0x00CA,0x00CB,0x0112,0x0114,0x0116,0x0118,0x011A]),
        (u"e",  [0x00E8,0x00E9,0x00EA,0x00EB,0x0113,0x0115,0x0117,0x0119,0x011B]),
        (u"G",  [0x011C,0x011E,0x0120,0x0122]),
        (u"g",  [0x011D,0x011F,0x0121,0x0123]),
        (u"H",  [0x0124,0x0126]),
        (u"h",  [0x0125,0x0127]),
        (u"I",  [0x00CC,0x00CD,0x00CE,0x00CF,0x0128,0x012A,0x012C,0x012E,0x0130]),
        (u"i",  [0x00EC,0x00ED,0x00EE,0x00EF,0x0129,0x012B,0x012D,0x012F,0x0131]),
        (u"IJ", [0x0132]),
        (u"ij", [0x0133]),
        (u"J",  [0x0134]),
        (u"j",  [0x0135]),
        (u"K",  [0x0136]),
        (u"k",  [0x0137,0x0138]),
        (u"L",  [0x0139,0x013B,0x013D,0x013F,0x0141]),
        (u"l",  [0x013A,0x013C,0x013E,0x0140,0x0142]),
        (u"N",  [0x00D1,0x0143,0x0145,0x0147,0x014A]),
        (u"n",  [0x00F1,0x0144,0x0146,0x0148,0x0149,0x014B]),
        (u"O",  [0x00D2,0x00D3,0x00D4,0x00D5,0x00D6,0x00D8,0x014C,0x014E,0x0150]),
        (u"o",  [0x00F2,0x00F3,0x00F4,0x00F5,0x00F6,0x00F8,0x014D,0x014F,0x0151]),
        (u"OE", [0x0152]),
        (u"oe", [0x0153]),
        (u"R",  [0x0154,0x0156,0x0158]),
        (u"r",  [0x0155,0x0157,0x0159]),
        (u"S",  [0x015A,0x015C,0x015E,0x0160]),
        (u"s",  [0x015B,0x015D,0x015F,0x01610,0x017F]),
        (u"T",  [0x0162,0x0164,0x0166]),
        (u"t",  [0x0163,0x0165,0x0167]),
        (u"U",  [0x00D9,0x00DA,0x00DB,0x00DC,0x0168,0x016A,0x016C,0x016E,0x0170,0x172]),
        (u"u",  [0x00F9,0x00FA,0x00FB,0x00FC,0x0169,0x016B,0x016D,0x016F,0x0171]),
        (u"W",  [0x0174]),
        (u"w",  [0x0175]),
        (u"Y",  [0x00DD,0x0176,0x0178]),
        (u"y",  [0x00FD,0x00FF,0x0177]),
        (u"Z",  [0x0179,0x017B,0x017D]),
        (u"z",  [0x017A,0x017C,0x017E])
        ]
    global _reptable
    for repchar,codes in _corresp :
        for code in codes :
            _reptable[code] = repchar

_fill_reptable()

def delete_diacritics(s) :
    """
    Delete accent marks.

    @param s: string to clean
    @type s: unicode
    @return: cleaned string
    @rtype: unicode
    """
    if isinstance(s, str):
        s = unicode(s, "utf8", "replace")
    ret = []
    for c in s:
        ret.append(_reptable.get(ord(c) ,c))
    return u"".join(ret)


# FIXME: Change this class name
class ldapUserGroupControl:
    """
    Control of User/Group/Computer(smb) control via LDAP
    this class create

    When instantiaciate, this class create an admin connection on ldap.
    After that, we have two members:
     - self.config: ConfigParser of main config file
     - self.l: bind on ldap with admin privilege
    """

    def getSalt(self):
        """generate salt for password crypt"""
        salt = ""
        for j in range(2):
            i = random.randint(0,9) % 3
            if i == 0 :
                i = (random.randint(0,9) % 11)
            elif i == 1 :
                i = (random.randint(0,9) % 25)
            elif i == 2 :
                i = (random.randint(0,9) % 25)
            salt = salt + str(i)
        return (salt)


    def _setDefaultConfig(self):
        """
        Set default config options.
        """
        self.gpoDN = "ou=System," + self.baseDN
        self.skelDir = "/etc/skel"
        self.defaultUserGroup = None
        self.defaultHomeDir = "/home"
        self.uidStart = 10000
        self.gidStart = 10000

    def __init__(self, conffile = None):
        """
        Constructor
        Create a LDAP connection on self.l with admin right
        Create a ConfigParser on self.config
        """
        if conffile: configFile = conffile
        else: configFile = INI
        self.conffile = conffile
        self.config = ConfigParser.ConfigParser()

        self.config.read(configFile)

        self.logger = logging.getLogger()

        # FIXME: get rid of this globals
        global ldapHost
        global baseDN
        global baseGroupsDN

        ldapHost = self.config.get("ldap", "host")
        baseDN = self.config.get("ldap", "baseDN")
        baseGroupsDN = self.config.get("ldap", "baseGroupsDN")

        self.ldapHost = ldapHost
        self.baseComputersDN = self.config.get("ldap", "baseComputersDN")
        self.baseUsersDN = self.config.get("ldap", "baseUsersDN").replace(" ", "")
        self.baseDN = baseDN.replace(" ", "")
        self.baseGroupsDN = baseGroupsDN.replace(" ", "")

        self.userHomeAction = self.config.getboolean("ldap", "userHomeAction")

        self._setDefaultConfig()

        # FIXME: configuration should be put in a dictionary ...
        try: self.gpoDN = self.config.get("ldap", "gpoDN")
        except: pass
        try: self.defaultUserGroup = self.config.get("ldap", "defaultUserGroup")
        except: pass
        try: self.skelDir = self.config.get("ldap", "skelDir")
        except: pass
        try: self.defaultHomeDir = self.config.get("ldap", "defaultHomeDir")
        except: pass
        try: self.uidStart = self.config.getint("ldap", "uidStart")
        except: pass
        try: self.gidStart = self.config.getint("ldap", "gidStart")
        except: pass

        try:
            listHomeDir = self.config.get("ldap", "authorizedHomeDir")
            self.authorizedHomeDir = listHomeDir.replace(' ','').split(',')
        except:
            self.authorizedHomeDir = [self.defaultHomeDir]

        # Fill dictionnary of hooks from config
        self.hooks = {}
        if self.config.has_section("hooks"):
            for option in self.config.options("hooks"):
                self.hooks["base." + option] = self.config.get("hooks", option)

        self.userDefault = {}
        self.userDefault["base"] = {}
        USERDEFAULT = "userdefault"
        if self.config.has_section(USERDEFAULT):
            for option in self.config.options(USERDEFAULT):
                self.userDefault["base"][option] = self.config.get(USERDEFAULT, option)
        
        self.l = ldap.open(ldapHost)

        # you should set this to ldap.VERSION2 if you're using a v2 directory
        self.l.protocol_version = ldap.VERSION3

        username = self.config.get("ldap", "rootName")
        password = self.config.get("ldap", "password")

        # Any errors will throw an ldap.LDAPError exception
        self.l.simple_bind_s(username, password)

    def runHook(self, hookName, uid = None, password = None):
        """
        Run a hook.
        """
        if self.hooks.has_key(hookName):
            self.logger.info("Hook " + hookName + " called.")
            if uid:
                # Make a temporary ldif file with user entry if an uid is specified
                fd, tmpname = tempfile.mkstemp()
                try:
                    fob = os.fdopen(fd, "wb")
                    result_set = self.search("uid=" + uid, self.baseUsersDN, None, ldap.SCOPE_ONELEVEL)
                    dn = result_set[0][0][0]
                    entries = result_set[0][0][1]
                    if password:
                        # Put user password in clear text in ldif
                        entries["userPassword"] = [password]
                    writer = ldif.LDIFWriter(fob)
                    writer.unparse(dn, entries)
                    fob.close()
                    lmctools.shlaunch(self.hooks[hookName] + " " + tmpname)
                finally:
                    os.remove(tmpname)
            else:
                lmctools.shlaunch(self.hooks[hookName])

    def enableUser(self, login):
        """
        Enable user by setting his/her shell to /bin/bash

        @param login: login of the user
        @type login: str
        """
        dn = 'uid=' + login + ',' + self.baseUsersDN
        s = self.l.search_s(dn, ldap.SCOPE_BASE)
        c, old = s[0]
        new = old.copy()
        new["loginShell"] = "/bin/bash" # FIXME: should not be hardcoded but put in a conf file
        modlist = ldap.modlist.modifyModlist(old, new)
        self.l.modify_s(dn, modlist)
        return 0

    def disableUser(self, login):
        """
        Disable user by setting his/her shell to /bin/false

        @param login: login of the user
        @type login: str
        """
        dn = 'uid=' + login + ',' + self.baseUsersDN
        s = self.l.search_s(dn, ldap.SCOPE_BASE)
        c, old = s[0]
        new = old.copy()
        new["loginShell"] = "/bin/false" # FIXME: should not be hardcoded but put in a conf file
        modlist = ldap.modlist.modifyModlist(old, new)
        self.l.modify_s(dn, modlist)
        return 0

    def isEnabled(self, login):
        """
        Return True if the user is enabled, else False.
        An user is enabled if his/her shell is not /bin/false
        """
        u = self.getDetailedUser(login)
        return u["loginShell"] != ["/bin/false"]

    def isLocked(self, login):
        """
        Return True if the user is locked, else False.
        An user is locked if there is a L in its samba account flags
        """
        u = self.getDetailedUser(login)
        try:
            ret = "L" in u["sambaAcctFlags"][0]
        except KeyError, IndexError:
            ret = False
        return ret

    def addUser(self, uid, password, firstN, lastN, homeDir = None, primaryGroup = None):
        """
        Add an user in ldap directory

        accent remove for gecos entry in ldap directory

        @param uid: login of the user
        @type uid: str

        @param password: user's password
        @type password : str

        @param firstN: unicode string with first name
        @type firstN: str

        @param lastN: unicode string with last name
        @type lastN: str

        @param homeDir: home directory of the user. If empty or None, default to defaultHomeDir/uid
        @type homeDir: str

        @param primaryGroup: primary group of the user. If empty or None, default to defaultUserGroup
        @type primaryGroup: str
        """
        # Make a homeDir string if none was given
        if not homeDir: homeDir = os.path.join(self.defaultHomeDir, uid)
        if not self.isAuthorizedHome(os.path.realpath(homeDir)):
            raise Exception(homeDir+"is not an authorized home dir.")

        uidNumber=self.maxUID() + 1

        # Get a gid number
        if not primaryGroup:
            if self.defaultUserGroup:
                primaryGroup = self.defaultUserGroup
            else:
                primaryGroup = uid
                if self.addGroup(uid) == -1:
                    raise Exception('group error: already exist or cannot instanciate')
        gidNumber = self.getDetailedGroup(primaryGroup)["gidNumber"][0]

        # Put default value in firstN and lastN
        if not firstN: firstN = uid
        if not lastN: lastN = uid

        # For the gecos LDAP field, make a full ASCII string
        gecosFirstN=str(delete_diacritics((firstN.encode("UTF-8"))))
        gecosLastN=str(delete_diacritics((lastN.encode("UTF-8"))))
        gecos = gecosFirstN + ' ' + gecosLastN

        # Build a UTF-8 representation of the unicode strings
        lastN = str(lastN.encode("utf-8"))
        firstN = str(firstN.encode("utf-8"))

        # If the passwd has been encoded in the XML-RPC stream, decode it
        if isinstance(password, xmlrpclib.Binary):
            password = str(password)

        # Create insertion array in ldap dir
        # FIXME: document shadow attributes choice
        user_info = {'loginShell':'/bin/bash',
                     'userPassWord':"{crypt}" + crypt.crypt(password, self.getSalt()),
                     'uidNumber':str(uidNumber),
                     'gidnumber':str(gidNumber),
                     'objectclass':('inetOrgPerson','posixAccount','shadowAccount','top','person'),
                     'uid':uid,
                     'gecos':gecos,
                     'cn': firstN + " " + lastN,
                     'displayName': firstN + " " + lastN,
                     'sn':lastN,
                     'givenName':firstN,
                     'homeDirectory' : homeDir,
                     'shadowExpire':'0', # Password never expire
                     'shadowInactive':'-1',
                     'shadowWarning':'7',
                     'shadowMin':'-1',
                     'shadowMax':'99999',
                     'shadowFlag':'134538308',
                     'shadowLastChange':'11192',
                     }

        try:
            # Set default attributes
            # FIXME: should be put elsewhere
            for attribute, value in self.userDefault["base"].items():
                # Search if modifiers have been specified
                s = re.search("^\[(.*)\]", value)
                if s:
                    modifiers = s.groups()[0]
                    # Remove modifiers from the string
                    value = re.sub("^\[.*\]", "", value)
		else: modifiers = ""
                # Interpolate value
                if "%" in value:
                    for a, v in user_info.items():
                        if type(v) == str:
                            if "/" in modifiers: v = delete_diacritics(v)
                            if "_" in modifiers: v = v.lower()
                            if "|" in modifiers: v = v.upper()
                            value = value.replace("%" + a + "%", v)
                if value == "DELETE":
                    for key in user_info.keys():
                        if key.lower() == attribute:
                            del user_info[key]
                            break
                elif value.startswith("+"):
                    for key in user_info.keys():
                        if key.lower() == attribute:
                            user_info[key] = user_info[key] + tuple(value[1:].split(","))
                            break
                else:
                    found = False
                    for key in user_info.keys():
                        if key.lower() == attribute:
                            user_info[key] = value
                            found = True
                            break
                    if not found: user_info[attribute] = value                

            ident = 'uid=' + uid + ',' + self.baseUsersDN
            # Search Python unicode string and encode them to UTF-8
	    attributes = []
	    for k,v in user_info.items():
	        fields = []
		if type(v) == list:
                    for item in v:
                        if type(item) == unicode: item = item.encode("utf-8")
                        fields.append(item)
                    attributes.append((k, fields))
                elif type(v) == unicode:
                    attributes.append((k, v.encode("utf-8")))
                else:
                    attributes.append((k, v))

            # Write into the directory
            self.l.add_s(ident, attributes)
            # Add user to her/his group primary group
            self.addUserToGroup(primaryGroup, uid)
        except ldap.LDAPError, error:
            # if we have a problem, we delete the group
            if not self.defaultUserGroup:
                self.delGroup(uid)
            # create error message
            raise error

        # creating home directory
        if self.userHomeAction:
            shutil.copytree('/etc/skel', homeDir, symlinks = True)
            lmctools.launch('chown', ['chown', '-R', str(uidNumber) + ':' + str(gidNumber), homeDir])

        # Run addUser hook
        self.runHook("base.adduser", uid, password)
        return 0

    def isAuthorizedHome(self,home):
        for ahome in self.authorizedHomeDir:
            if ahome in home:
                return True
        return False

    def addMachine(self, uid, comment, addMachineScript = False):
        """
        Add a computer in the PDC control

        @param uid: name of new machine (no space)
        @type uid: str

        @param comment: comment of machine (full string accept)
        @type comment: str

        """
        # add '$' to be in accord with samba policy
        origuid = uid
        uid=uid+'$'
        uidNumber=self.maxUID()+1;

        if (comment==''):
            comment="aucun";

        # shadowAccount require an userPassword attribute
        password="4r5t40e"
        comment_UTF8=str(delete_diacritics((comment.encode("UTF-8"))))
        # creating machine skel
        user_info = {'shadowMin':'-1',
                    'uid':uid,
                    'uidNumber':str(uidNumber),
                    'gidnumber':'100',
                    'loginShell':'/bin/false',
                    'shadowFlag':'134538308',
                    'shadowExpire':'-1',
                    'shadowMax':'99999',
                    'objectclass':('account','posixAccount','shadowAccount','top'),
                    'gecos':str(comment_UTF8),
                    'shadowLastChange':'11192',
                    'userPassWord':"{crypt}" + crypt.crypt(password, self.getSalt()),
                    'cn':uid,
                    'shadowInactive':'-1',
                    'shadowWarning':'7',
                    'homeDirectory':'/home/machine'
                     }

        ident = 'uid=' + uid + ',' + self.baseComputersDN
        attributes=[ (k,v) for k,v in user_info.items() ]
        self.l.add_s(ident,attributes)

        if not addMachineScript:
            cmd = 'smbpasswd -a -m '+uid
            shProcess = generateBackgroundProcess(cmd)
            ret = shProcess.getExitCode()

            if ret != 0:
                delMachine(origuid) #del machine we just create
                raise Exception("Failed to add computer entry\n"+shProcess.stdall)

        return 0

    def addGroup(self, cn):
        """
        Add a group in an ldap directory

        @param cn: group name.
            We just precise the name, complete path for group is define
            in config file.
        @type cn: str
        """

        maxgid = self.maxGID()
        gidNumber = maxgid + 1;

        # creating group skel
        group_info = {'cn':cn,
                    'gidnumber':str(gidNumber),
                    'objectclass':('posixGroup','top')
                     }
        try:
            entry = 'cn=' + cn + ',' + baseGroupsDN
            attributes = [ (k,v) for k,v in group_info.items() ]
            self.l.add_s(entry, attributes)
        except ldap.LDAPError, error:
            raise lmcException(error)
        return gidNumber

    def delUserFromGroup(self,cngroup,uiduser):
        """
         Remove an user from a posixGroup account in ldapdir

         remove memberUid in ldap entry attributes

         @param cngroup: name of the group (not full ldap path)
         @type cngroup: unicode

         @param uiduser: user uid (not full ldap path)
         @type uiduser: unicode
        """
        cngroup = cngroup.encode("utf-8")
        uiduser = uiduser.encode("utf-8")
        self.l.modify_s('cn='+cngroup+','+baseGroupsDN, [(ldap.MOD_DELETE,'memberUid',uiduser)])
        return 0

    def delUserFromAllGroups(self, uid):
        """
        Remove an user from all groups in the LDAP

        @param uid: login of the user
        @type uid: unicode
        """
        ret = self.search("memberUid=" + uid, self.baseGroupsDN)

        if ret:
            for result in ret:
                group = result[0][1]["cn"][0]
                self.delUserFromGroup(group.decode("utf-8"), uid)
        return 0

    def changeUserPrimaryGroup(self, uid, group):
        """
        Change the primary group of a user

        @param uid: login of the user
        @type uid: unicode

        @param group: new primary group
        @type uid: unicode
        """
        gidNumber = self.getDetailedGroup(group)["gidNumber"][0]
        currentPrimary = self.getUserPrimaryGroup(uid)
        try:
            self.delUserFromGroup(currentPrimary, uid)
        except ldap.NO_SUCH_ATTRIBUTE:
            # Try to delete the user from a group where the she/he is not
            # Can be safely passed
            pass
        self.addUserToGroup(group, uid)
        self.changeUserAttributes(uid, "gidNumber", gidNumber)

    def getAllGroupsFromUser(self, uid):
        """
        Get all groups that own this user

        @param uid: login of the user
        @type uid: unicode
        """
        ret = self.search("memberUid=" + uid, self.baseGroupsDN)
        resArray = []
        if ret:
            for result in ret:
                group = result[0][1]["cn"][0]
                resArray.append(group)

        return resArray

    def getUserPrimaryGroup(self, uid):
        """
        Return the primary group of a user

        @param uid: user uid
        @type uid: unicode

        @return: the name of the group
        @rtype: unicode
        """
        gidNumber = self.getDetailedUser(uid)["gidNumber"][0]
        return self.getDetailedGroupById(gidNumber)["cn"][0]

    def getUserSecondaryGroups(self, uid):
        """
        Return the secondary groups of a user

        @param uid: user uid
        @type uid: unicode

        @return: a list of the name of the group
        @rtype: unicode
        """
        primary = self.getUserPrimaryGroup(uid)
        secondary = self.getAllGroupsFromUser(uid)
        try:
            secondary.remove(primary)
        except ValueError:
            # The primary group is not listed in the secondary groups
            pass
        return secondary

    def addUserToGroup(self, cngroup, uiduser, base = None):
        """
         add memberUid attributes corresponding param user to an ldap posixGroup entry

         @param cngroup: name of the group (not full ldap path)
         @type cngroup: unicode

         @param uiduser: user uid (not full ldap path)
         @type uiduser: unicode
         """
        if not base: base = self.baseGroupsDN
        cngroup = cngroup.encode("utf-8")
        uiduser = uiduser.encode("utf-8")
        try:
            self.l.modify_s('cn=' + cngroup + ',' + base, [(ldap.MOD_ADD, 'memberUid', uiduser)])
        except ldap.TYPE_OR_VALUE_EXISTS:
            # Try to add a the user to one of his/her group
            # Can be safely ignored
            pass
        return 0

    def changeUserAttributes(self,uid,attr,attrVal):
        """
        Change an user attribute.
        If an attrVal is empty, the attribute will be removed.

        @param uid: uid of this user (not full ldap path)
        @type  uid: str

        @param attr: attribute name
        @type  attr: str

        @param attrVal: attribute value
        @type  attrVal: object
        """
        if attrVal:            
            if type(attrVal) == unicode:
                attrVal = attrVal.encode("utf-8")
            elif isinstance(attrVal, xmlrpclib.Binary):
                # Needed for binary string coming from XMLRPC
                attrVal = str(attrVal)
            self.l.modify_s('uid='+uid+','+ self.baseUsersDN, [(ldap.MOD_REPLACE,attr,attrVal)])
        else:
            # Remove the attribute because its value is empty
            try:
                self.l.modify_s('uid='+uid+','+ self.baseUsersDN, [(ldap.MOD_DELETE,attr, None)])
            except ldap.NO_SUCH_ATTRIBUTE:
                # The attribute has been already deleted
                pass

    def changeGroupAttributes(self, group, attr, attrVal):
        """
         change a group attributes

         @param group: group name
         @type  group: str

         @param attr: attribute name
         @type  attr: str

         @param attrVal: attribute value
         @type  attrVal: object
        """
        group = group.encode("utf-8")
        if attrVal:
            attrVal = str(attrVal.encode("utf-8"))
            self.l.modify_s('cn=' + group + ','+ self.baseGroupsDN, [(ldap.MOD_REPLACE,attr,attrVal)])
        else:
            self.l.modify_s('cn=' + group + ','+ self.baseGroupsDN, [(ldap.MOD_REPLACE,attr,'rien')])
            self.l.modify_s('cn=' + group + ','+ self.baseGroupsDN, [(ldap.MOD_DELETE,attr,'rien')])
        return 0

    def changeUserPasswd(self, uid, passwd):
        """
         crypt user password and change it

         @param uid: user name
         @type  uid: str

         @param passwd: non encrypted password
         @type  passwd: str
        """
        # If the password has been encoded in the XML-RPC stream, decode it
        if isinstance(passwd, xmlrpclib.Binary):
            passwd = str(passwd)
        
        passwdCrypt="{crypt}" + crypt.crypt(passwd, self.getSalt())
        self.l.modify_s('uid='+uid+','+ self.baseUsersDN, [(ldap.MOD_REPLACE,'userPassWord',passwdCrypt)])
        return 0

    def delUser(self, uid, home):
        """
        Delete an user
        @param uid: uid of the user.
        @type  uid: str

        @param home: if =1 delete home directory
        @type  home: int
        """
        # Run delUser hook
        self.runHook("base.deluser", uid)

        if home and self.userHomeAction:
            homedir = self.getDetailedUser(uid)['homeDirectory'][0]
            lmctools.shlaunch('rm -rf ' + homedir)

        self.delRecursiveEntry('uid=' + uid + ',' + self.baseUsersDN)

        return 0

    def delRecursiveEntry(self,path):
        """
        Delete an entry, del recursive leaf

        @param path: credential name in an ldap directory
            ex: "cn=admin, ou=Users, ou=ExObject, dc = lo2k, dc= net"
        @type path: str
        """

        #getAllLeaf and delete it
        for entry in self.getAllLeafs(path):
            self.delRecursiveEntry(entry)

        try:
            self.l.delete_s(path)
        except ldap.LDAPError, e:
            errObj = errorMessage('ldapUserGroupControl::delRecursiveEntry()')
            errObj.addMessage("error: deleting "+path)
            errObj.addMessage('ldap.LDAPError:')
            errObj.addMessage(e)
            return errObj.errorArray()
        return 0


    def getAllLeafs(self,path):
        """
         return all leafs of a specified path

            @param path: credential name in an ldap directory
            ex: "ou=addr, cn=admin, ou=Users, ou=ExObject, dc = lo2k, dc= net"

        """
        searchScope = ldap.SCOPE_ONELEVEL

        try:
            ldap_result_id = self.l.search(path, searchScope)
            result_set = []
            while 1:
                result_type, result_data = self.l.result(ldap_result_id, 0)
                if (result_data == []):
                    break
                else:
                    if result_type == ldap.RES_SEARCH_ENTRY:
                        result_set.append(result_data)

        except ldap.LDAPError, e:
            print e

        #prepare array for processing
        resArr=[]

        for i in range(len(result_set)):
            for entry in result_set[i]:
                    resArr.append(entry[0])

        resArr.sort()

        return resArr

    def delMachine(self,uidUser):
        """
        Remove a computer in the PDC. (Just ldap action)

         @param uidUser: computer name
         @type  uidUser: str

        """
        uidUser = uidUser + "$"

        self.l.delete_s('uid='+uidUser+','+ self.baseComputersDN)
        return 0

    def delGroup(self, cnGroup):
        """
         remove a group
         /!\ baseGroupsDN based on INI file
         @param cnGroup: group name (not full ldap path)
         @type  cnGroup: str

        """
        if self.existUser(cnGroup): return -1
        try :
            self.l.delete_s('cn='+cnGroup+','+baseGroupsDN)
            return 0
        except ldap.LDAPError, e:
            return e

    def getEntry(self, dn):
        """
        Return a raw LDAP entry
        """
        attrs = []
        attrib = self.l.search_s(dn, ldap.SCOPE_BASE)
        c, attrs = attrib[0]
        newattrs = copy.deepcopy(attrs)
        return newattrs

    def getDetailedUser(self, uid, base = None):
        """
         Return raw ldap info on user

         @param uid: user name
         @type uid: str

         @return: full raw ldap array (dictionnary of lists)
         @type: dict

        """
        if not base: base = self.baseUsersDN
        cn = 'uid=' + str(uid) + ', ' + base
        attrs = []
        attrib = self.l.search_s(cn, ldap.SCOPE_BASE)

        c,attrs=attrib[0]

        newattrs = copy.deepcopy(attrs)

        return newattrs

    def getDetailedGroup(self, group, base = None):
        """
         Return raw ldap info on a group

         @param group: group name
         @type group: str

         @return: full raw ldap array (dictionnary of lists)
         @type: dict

        """
        if not base: base = self.baseGroupsDN
        cn = 'cn=' + group.encode("utf-8") + ', ' + base
        attrs = []
        attrib = self.l.search_s(cn, ldap.SCOPE_BASE)
        c,attrs=attrib[0]
        newattrs = copy.deepcopy(attrs)
        return newattrs

    def getDetailedGroupById(self, id, base = None):
        """
         Return raw ldap info on a group

         @param uid: gidNumber
         @type uid: str

         @return: full raw ldap array (dictionnary of lists)
         @type: dict
        """
        ret = self.search("gidNumber=" + str(id), self.baseGroupsDN)
        resArray = []
        if ret:
            for result in ret:
                c,attrs=result[0]
                newattrs = copy.deepcopy(attrs)
                return newattrs


        #if not base: base = self.baseGroupsDN
        #print "search group uid "+id
#         pattern = 'gidNumber=' + str(id) + ', ' + base
#         print "recherche pattern " + pattern
#         attrs = []
#         attrib = self.l.search_s(pattern, ldap.SCOPE_BASE)
#
#         c,attrs=attrib[0]
#
#         newattrs = copy.deepcopy(attrs)

        return newattrs

    def getUserGroups(self,pattern):
        """
        return all groups who contain memberUid of this user

        @param pattern: search pattern
        @type pattern: str

        @return: return list with all groups who contain memberUid of pattern user
        @rtype: list
        """
        searchScope = ldap.SCOPE_SUBTREE
        retrieveAttributes = None

        searchFilter = "memberUid=" + pattern

        try:
            ldap_result_id = self.l.search(baseGroupsDN, searchScope, searchFilter, retrieveAttributes)
            result_set = []
            while 1:
                result_type, result_data = self.l.result(ldap_result_id, 0)
                if (result_data == []):
                    break
                else:
                    if result_type == ldap.RES_SEARCH_ENTRY:
                        result_set.append(result_data)

        except ldap.LDAPError, e:
            print e

        # prepare array for processing
        resArr=[]

        for i in range(len(result_set)):
            for entry in result_set[i]:
                try:
                    cn = entry[1]['cn'][0]
                    resArr.append(cn)
                except:
                    pass

        resArr = cSort(resArr);
        return resArr

    def search(self, searchFilter = '', basedn = None, attrs = None, scope = ldap.SCOPE_SUBTREE):
        """
        @param searchFilter: LDAP search filter
        @type searchFilter: unicode
        """
        searchFilter = searchFilter.encode("utf-8")
        if not basedn: basedn = self.baseDN
        result_set = []
        ldap_result_id = self.l.search(basedn, scope, searchFilter, attrs)
        while 1:
            try:
                result_type, result_data = self.l.result(ldap_result_id, 0)
            except ldap.NO_SUCH_OBJECT:
                result_data = []
            if (result_data == []):
                break
            else:
                if result_type == ldap.RES_SEARCH_ENTRY:
                    result_set.append(result_data)

        return result_set

    def searchUser(self, pattern = '', base = None):
        """
        search a user in ldapdirectory
        @param pattern : pattern for search filter
          ex: *admin*, luc*
        @type pattern : str

         if empty, return all user

        search begin at baseUsersDN (defines in INIFILE)

        @return: list of all users correspond criteria
        @rtype: list
        """
        if (pattern==''): pattern = "*"
        return self.searchUserAdvance("uid="+pattern,base)

    def searchUserAdvance(self, pattern = '', base = None):
        """
        search a user in ldapdirectory
        @param pattern : pattern for search filter
          ex: *admin*, luc*
        @type pattern : str

         if empty, return all user

        search begin at baseUsersDN (defines in INIFILE)

        @return: list of all users correspond criteria
        @rtype: list
        """
        if not base: base = self.baseUsersDN
        if (pattern==''): searchFilter = "uid=*"
        else: searchFilter = pattern
        result_set = self.search(searchFilter, base, None, ldap.SCOPE_ONELEVEL)

        # prepare array for processing
        resArr = []
        uids = []
        for i in range(len(result_set)):
            for entry in result_set[i]:
                localArr= {}
                # FIXME: field list should not be hardcoded
                for field in ["uid", "gecos", "homeDirectory", "sn", "givenName", "mail", "telephoneNumber"]:
                    try:
                        localArr[field] = entry[1][field][0]
                    except KeyError:
                        # If the field does not exist, put an empty value
                        localArr[field] = ""

                localArr["obj"] = entry[1]['objectClass']

                shell = entry[1]["loginShell"][0]
                enabled = 0
                if shell != "/bin/false": enabled = 1
                localArr["enabled"] = enabled

                #if user not contain "$" for first character
                if (re.search('([^$])$',localArr["uid"])):
                    resArr.append(localArr)
                    uids.append(localArr["uid"])

        uids = cSort (uids)
        ret = []
        for uid in uids:
            for l in resArr:
                if l["uid"] == uid:
                    ret.append(l)
                    break

        return ret

    def getMembers(self,group):
        """
        return all member of a specified group

        @param group: group name
        @type group: str

        @return: return memberuid attribute.
        @rtype: list
        """
        result_set = self.search("cn=" + group, baseGroupsDN, None, ldap.SCOPE_ONELEVEL)

        # prepare array for processing
        resArr=[]

        for i in range(len(result_set)):
            for entry in result_set[i]:
                try:
                    resArr = entry[1]['memberUid']

                except:
                    pass

        resArr = cSort(resArr)
        return resArr

    def existUser(self, uid):
        """
        Test if the user exists in the LDAP.

        @param uid: user uid
        @type uid: str

        @return: return True if a user exist in the ldap BaseDN directory
        @rtype: boolean
        """
        uid = uid.strip()
        ret = False
        if len(uid):
            ret = len(self.searchUser(uid)) == 1
        return ret

    def existGroup(self, group):
        """
        Test if the group exists in the LDAP.

        @param group: group name
        @type group: str

        @return: return True if a group exist in the LDAP directory
        @rtype: boolean
        """
        group = group.strip()
        ret = False
        if len(group):
            ret = len(self.searchGroup(group)) == 1
        return ret

    def searchGroup(self, pattern = '' , base = None, minNumber = 0):
        if not base: base = self.baseGroupsDN
        if (pattern==''): searchFilter = "cn=*"
        else: searchFilter = "cn=" + pattern
        result_set = self.search(searchFilter, base, None, ldap.SCOPE_ONELEVEL)

        # prepare array for processing
        resArr = {}

        for i in range(len(result_set)):
            for entry in result_set[i]:

                try:
                    cn = entry[1]['cn'][0]

                    try:
                        description = entry[1]['description'][0]
                    except:
                        description = ''

                    gidNumber = int(entry[1]['gidNumber'][0])

                    try:
                        numbr = len(entry[1]['memberUid'])
                    except:
                        numbr = 0;

                    cell = []

                    cell.append(cn)
                    cell.append(description)
                    cell.append(numbr)

                    if (gidNumber >= minNumber): resArr[cn.lower()] = cell

                except:
                    pass

        return resArr

    def maxUID(self):
        """
        fetch maxUID

        @return: maxUid in ldap directory
        @rtype: int
        """
        ret = []
        ret.append(self.search("uid=*", self.baseUsersDN, None, ldap.SCOPE_ONELEVEL))
        ret.append(self.search("uid=*", self.baseComputersDN, None, ldap.SCOPE_ONELEVEL))

        # prepare array for processing
        maxuid = 0
        for result_set in ret:
            for i in range(len(result_set)):
                for entry in result_set[i]:

                    try:
                        uidNumber = int(entry[1]['uidNumber'][0])
                    except KeyError:
                        uidNumber = -1

                    if (maxuid <= uidNumber):
                        maxuid = uidNumber

            if maxuid < self.uidStart: maxuid = self.uidStart

        return maxuid

    def removeUserObjectClass(self, uid, className):
        # Create LDAP path
        cn = 'uid=' + uid + ', ' + self.baseUsersDN
        attrs= []
        attrib = self.l.search_s(cn, ldap.SCOPE_BASE)

        # fetch attributes
        c,attrs=attrib[0]
        # copy new attrs
        newattrs = copy.deepcopy(attrs)

        if (className in newattrs["objectClass"]):
            indexRm = newattrs["objectClass"].index(className)
            del newattrs["objectClass"][indexRm]

        # For all element we can try to delete
        for entry in self.getAttrToDelete(cn, className):
            for k in newattrs.keys():
                if k.lower()==entry.lower():
                    del newattrs[k] #delete it

        # Apply modification
        mlist = ldap.modlist.modifyModlist(attrs, newattrs)
        self.l.modify_s(cn, mlist)

    def removeGroupObjectClass(self, group, className):
        # Create LDAP path
        group = group.encode("utf-8")
        cn = 'cn=' + group + ', ' + self.baseGroupsDN
        attrs= []
        attrib = self.l.search_s(cn, ldap.SCOPE_BASE)

        # fetch attributes
        c,attrs=attrib[0]
        # copy new attrs
        newattrs = copy.deepcopy(attrs)

        if (className in newattrs["objectClass"]):
            indexRm = newattrs["objectClass"].index(className)
            del newattrs["objectClass"][indexRm]

        # For all element we can try to delete
        for entry in self.getAttrToDelete(cn, className):
            for k in newattrs.keys():
                if k.lower()==entry.lower():
                    del newattrs[k] #delete it

        # Apply modification
        mlist = ldap.modlist.modifyModlist(attrs, newattrs)
        self.l.modify_s(cn, mlist)

    def getAttrToDelete(self, dn, className):
        """retrieve all attributes to delete wich correspond to param schema"""

        arrObjectList = self.getEntry(dn)["objectClass"]
        indexRm = arrObjectList.index(className);

        # Remove deleting objectList from getSchema routine
        del arrObjectList[indexRm]

        attrList = self.getSchema(className)

        badList = Set()
        for schemaName in arrObjectList:
            badList = badList | self.getSchema(schemaName)

        attrList = attrList - badList

        return attrList

    def getSchema(self,schemaName):
        """
         return schema corresponding schemaName
        @param schemaName: schema name
            ex: person, account, OxUserObject
        @type schemaName: str

        @return: schema parameters
        @type list

        for more info on return type, reference to ldap.schema
        """
        subschemasubentry_dn, schema = ldap.schema.urlfetch("ldap://" + self.ldapHost)
        schemaAttrObj = schema.get_obj(ldap.schema.ObjectClass,schemaName)
        if not schemaAttrObj is None:
            return ( Set(schemaAttrObj.must) | Set(schemaAttrObj.may) )
        else:
            return Set()

    def maxGID(self):
        """
        fetch maxGID

        @return: maxGid in ldap directory
        @rtype: int
        """
        result_set = self.search("cn=*", self.baseGroupsDN, None, ldap.SCOPE_ONELEVEL)
        maxgid = 0
        for i in range(len(result_set)):
            for entry in result_set[i]:
                try:
                    gidNumber = int(entry[1]['gidNumber'][0])
                except KeyError:
                    gidNumber = -1
                if maxgid <= gidNumber: maxgid = gidNumber
        if maxgid < self.gidStart: maxgid = self.gidStart
        return maxgid

    def moveHome(self,uid,newHome):
        """
         Move an home directory.

         @param uid: user name
         @type uid: str

         @param newHome: new home path
            ex: /home/coin
         @type newHome: str
        """
        oldHome = self.getDetailedUser(uid)['homeDirectory'][0]
        if (newHome == oldHome):
            return 0

        if self.userHomeAction:
            if not lmctools.shlaunch("mv "+oldHome+" "+newHome):
                self.changeUserAttributes(uid,"homeDirectory",newHome)
                return 0
            # else, with got an error
        else: self.changeUserAttributes(uid,"homeDirectory",newHome)

        return 1

    def addOu(self, ouname, ldappath):
        """
         add an organizational Unit to an ldap entry

         @param ouname: organizational unit name
         @type ouname: str

         @param ldappath: ldap full path
         @type ldappath: str
        """
        addrdn = 'ou=' + ouname + ', ' + ldappath
        addr_info = {'ou':ouname,
                    'objectClass':('organizationalUnit','top')}
        attributes=[ (k,v) for k,v in addr_info.items() ]

        self.l.add_s(addrdn,attributes)

###########################################################################################
############## ldap authentification
###########################################################################################

def ldapAuth(uiduser, passwd):
    """
    Authenticate an user with her/his password against a LDAP server.
    Return true if the user has been successfully authenticated, else false.
    """
    ldapObj = ldapAuthen(uiduser, passwd)
    return ldapObj.isRightPass()


class ldapAuthen:
    """
    class for LDAP authentification

    bind with constructor parameters to an ldap directory.
    bind return error if login/password give to constructor isn't valid
    """

    def __init__(self, login, password, conffile = None):
        """
        Initialise LDAP connection

        @param login: login
        @type login: str

        @param password: not encrypted password
        @type password: str

        Try a LDAP bind.

        self.result is True if the bind is successful
        If there are any error, self.result is False and a ldap
        exception will be raised.
        """
        if not conffile: conffile = INI
        config = ConfigParser.ConfigParser()
        config.read(conffile)

        baseDN = config.get("ldap", "baseUsersDN")
        ldapHost = config.get("ldap", "host")

        l = ldap.open(ldapHost)

        # connect to an ldap V3 (correct if not v3)
        l.protocol_version = ldap.VERSION3

        # if login == root, try to connect as the LDAP manager
        if (login == 'root'): username = config.get("ldap", "rootName")
        else: username = 'uid=' + login + ', ' + baseDN

        # If the passwd has been encoded in the XML-RPC stream, decode it
        if isinstance(password, xmlrpclib.Binary):
            password = str(password)

        self.result = False
        try:
            l.simple_bind_s(username, password)
            self.result = True
        except ldap.INVALID_CREDENTIALS:
            pass

    def isRightPass(self):
        """
        @return: Return True if the class constructor has successfully
        authenticated the user.
        @rtype: bool
        """
        return self.result


class GpoManager:

    def __init__(self, service, conffile = None, gpoCreate = True):
        """
        @param service: name of the service (sub ou of the GPO root)
        @param gpoCreate: If True, create the needed OU for GPO management of the service
        """
        self.l = ldapUserGroupControl(conffile)
        self.service = service
        if gpoCreate: self.addServiceOuGPO()

    def _getDN(self):
        return "ou=" + self.service + "," + self.l.gpoDN

    def _getGpoDN(self, gpoName):
        return "cn=" + gpoName + "," + self._getDN()

    def addRootGpoOu(self):
        """
        Add a main GPO organizational unit
        """
        try:
            self.l.addOu(self.l.gpoDN)
        except ldap.ALREADY_EXISTS, e:
            # The Ou already exists
            pass

    def addServiceOuGPO(self):
        """
        Add a main ou for the current service under main GPO ou.
        """
        try:
            self.l.addOu(self.service, self.l.gpoDN)
        except ldap.ALREADY_EXISTS, e:
            # The Ou already exists
            pass
        except ldap.STRONG_AUTH_REQUIRED, e:
            # We have this error if we try to write into a replicat
            # Just ignore
            pass

    def add(self, gpoName, ACLs):
        """
        Add a GPO

        @param gpoName: Name of the GPO
        @param ACLs: ACLs dict
        @type ACLs: dict
        """
        # creating group skel
        group_info = {'cn':gpoName,
                    'objectclass':('GroupPolicy','top')
                     }
        group_info["ACL"] = []
        for aclname in ACLs:
            group_info["ACL"].append(aclname + ":" + ACLs[aclname])
        entry = 'cn=' + gpoName + ',' + self._getDN()
        attributes = [ (k,v) for k,v in group_info.items() ]
        self.l.l.add_s(entry, attributes)

    def delete(self, gpoName):
        """
        Delete a GPO

        @param gpoName: Name of the GPO
        """
        entry = 'cn=' + gpoName + ',' + self._getDN()
        self.l.l.delete_s(entry)

    # User GPO management methods

    def addUserToGPO(self, uid, gpoName):
        """
        Add an user to a GPO.

        The DN of the user is put in a member field of the GPO.

        @param gpoName: name of the GPO
        @uid: uid of the user name
        """
        dn = "uid=" + uid + "," + self.l.baseUsersDN
        try:
            self.l.l.modify_s( self._getGpoDN(gpoName), [(ldap.MOD_ADD, 'member', dn)])
        except ldap.TYPE_OR_VALUE_EXISTS:
            # Value already set
            pass

    def delUserFromGPO(self, uid, gpoName):
        """
        Del an user from a GPO.

        @param gpoName: name of the GPO
        @param uid: uid of the user name
        """
        dn = "uid=" + uid + "," + self.l.baseUsersDN
        try:
            self.l.l.modify_s(self._getGpoDN(gpoName), [(ldap.MOD_DELETE, 'member', dn)])
        except ldap.NO_SUCH_ATTRIBUTE:
            # Value already deleted
            pass

    def getUsersFromGPO(self, gpoName):
        """
        Return all members of a GPO
        """
        ret = self.l.search(searchFilter = "cn=" + gpoName, basedn = self._getDN(), attrs = ["member"])
        members = []
        for item in ret:
            attrs = item[0][1]
            try:
                for member in attrs["member"]:
                    if member.startswith("uid="): members.append(member)
            except KeyError:
                # There is no member in this group
                pass
        return members

    # Group GPO management methods

    def addGroupToGPO(self, group, gpoName):
        """
        Add a group to a GPO.

        The DN of the group is put in a member field of the GPO.

        @param group: group name
        @param gpoName: name of the GPO
        """
        dn = "cn=" + group + "," + self.l.baseGroupsDN
        try:
            self.l.l.modify_s( self._getGpoDN(gpoName), [(ldap.MOD_ADD, 'member', dn)])
        except ldap.TYPE_OR_VALUE_EXISTS:
            # Value already set
            pass

    def delGroupFromGPO(self, group, gpoName):
        """
        Del n group from a GPO.

        @param group: group name
        @param gpoName: name of the GPO
        """
        dn = "cn=" + group + "," + self.l.baseGroupsDN
        try:
            self.l.l.modify_s(self._getGpoDN(gpoName), [(ldap.MOD_DELETE, 'member', dn)])
        except ldap.NO_SUCH_ATTRIBUTE:
            # Value already deleted
            pass

    def getGroupsFromGPO(self, gpoName):
        """
        Return all group members of a GPO
        """
        ret = self.l.search(searchFilter = "cn=" + gpoName, basedn = self._getDN(), attrs = ["member"])
        members = []
        for item in ret:
            attrs = item[0][1]
            try:
                for member in attrs["member"]:
                    if member.startswith("cn="): members.append(member)
            except KeyError:
                # There is no member in this group
                pass
        return members

    # Other methods

    def getResourceGpo(self, dn, gpoName):
        """
        Return the resources name to which an user is member

        @param dn: user name or group name to search for(full DN)
        @param gpoName: name of the GPO to search for
        """
        ret = self.l.search(searchFilter = "cn=" + gpoName + "_*", basedn = self._getDN(), attrs = ["member"])
        resources = []
        for item in ret:
            cn = item[0][0]
            attrs = item[0][1]
            try:
                if dn in attrs["member"]:
                    resource = cn.split(",")[0].split("_")[1]
                    resources.append(resource)
            except KeyError:
                pass
        return resources




################################################################################
##########  command line section
################################################################################

def launch(s):
    """
     launch command and return the result

     @param s:command to launch
     @type s:list

     @result: list with each elements of the list is a row "\n" of result
     @rtype: list
    """
    ret = lmctools.shlaunch(s)

    return ret

################################################################################
###### LOG VIEW CLASS
################################################################################

class LogView:
    """
    LogView class. Provide accessor to show log content
    """

    def __init__(self, logfile = '/var/log/ldap.log', pattern=None):
        config = PluginConfig("base")
        try: self.logfile = config.get("ldap", "logfile")
        except NoSectionError, NoOptionError: self.logfile = logfile
        try: self.maxElt = config.get("LogView", "maxElt")
        except NoSectionError, NoOptionError: self.maxElt= 200
        self.file = open(self.logfile, 'r')
        if pattern:
            self.pattern = pattern
        else:
            self.pattern = {
                "slapd-syslog" : "^(?P<b>[A-z]{3}) *(?P<d>[0-9]+) (?P<H>[0-9]{2}):(?P<M>[0-9]{2}):(?P<S>[0-9]{2}) .* conn=(?P<conn>[0-9]+)\ (?P<opfd>op|fd)=(?P<opfdnum>[0-9]+) (?P<op>[A-Za-z]+) (?P<extra>.*)$",
                "fds-accesslog" : "^\[(?P<d>[0-9]{2})/(?P<b>[A-z]{3})/(?P<y>[0-9]{4}):(?P<H>[0-9]{2}):(?P<M>[0-9]{2}):(?P<S>[0-9]{2}) .*\] conn=(?P<conn>[0-9]+)\ (?P<opfd>op|fd)=(?P<opfdnum>[0-9]+) (?P<op>[A-Za-z]+)(?P<extra> .*|)$"
                }

    def getLog(self, filter=""):
        log = self.file.readlines()
        log.reverse()
        elts = []
        for line in log:
            if filter in line:
                elts.append(line)
        res = []
        for line in elts[0:self.maxElt]:
           parsed = self.parseLine(line)
           if parsed:
               res.append(parsed)
        return res

    def parseLine(self, line):
        ret = None
        patternKeys = self.pattern.keys()
        patternKeys.sort()
        # We try each pattern until we found one that works
        for pattern in patternKeys:
            sre = re.search(self.pattern[pattern], line)
            if sre:
                res = sre.groupdict()
                if res:
                    # Use current year if not set
                    if not res.has_key("Y"):
                        res["Y"] = str(localtime()[0])
                    timed = strptime("%s %s %s %s %s %s" % (res["b"], res["d"], res["Y"], res["H"], res["M"], res["S"]), "%b %d %Y %H %M %S")
                    res["time"] = mktime(timed)
                    ret = res
                    break
        return ret
