#!/usr/bin/env python2.5

import os, sys
import vobject

# google
import atom
import gdata.contacts.service

# Copyright (c) 2008 Philip Jackson <phil@shellarchive.co.uk>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.

# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.

__VERSION__ = "0.2"

VOBJECT_VDATA_COMPLEX_REL_MAP = [{
  "vcard_attr"   : "adr",
  "gobject_attr" : "postal_address",
  "gobject"      : {
    "class" : gdata.contacts.PostalAddress,
    "attr"  : "text"
    },
  "rel_map"      : {
    "Home"   : gdata.contacts.REL_HOME,
    "Mobile" : gdata.contacts.REL_WORK,
    None     : gdata.contacts.REL_OTHER,
    }
  },
  {
  "vcard_attr"   : "tel",
  "gobject_attr" : "phone_number",
  "gobject"      : {
    "class" : gdata.contacts.PhoneNumber,
    "attr"  : "text"
    },
  "rel_map"      : {
    "Home"   : gdata.contacts.PHONE_HOME,
    "Mobile" : gdata.contacts.PHONE_MOBILE,
    None     : gdata.contacts.PHONE_OTHER,
    }
  },
  {
  "vcard_attr"   : "email",
  "gobject_attr" : "email",
  "gobject"      : {
    "class" : gdata.contacts.Email,
    "attr"  : "address"
    },
  "rel_map"      : {
    None : gdata.contacts.REL_OTHER
    }
  }]

def merge_notes(gcontact, vcard):
  if hasattr(vcard, "note"):
    uitem = unicode(vcard.note.value)

    if not len(uitem):
      return 0

    if gcontact.content is None or gcontact.content.text != uitem:
      gcontact.content = atom.Content(text=uitem)

      print "notes added to %s: (%s)" % (
        gcontact.title.text, uitem )

      return 1

  return 0

def merge_org(gcontact, vcard):
  if hasattr(vcard, "org"):
    uitem = unicode(vcard.org.value[0])

    if not len(uitem):
      return 0

    if gcontact.organization is None \
          or gcontact.organization.org_name.text != uitem:
      gorg = gdata.contacts.Organization(org_name=gdata.contacts.OrgName(uitem))
      gcontact.organization = gorg

      print "organisation added to %s: (%s)" % (
        gcontact.title.text, uitem )

      return 1

  return 0

def merge_object_with_ref(gcontact, vcard, rel_map):
  vcard_attr   = rel_map["vcard_attr"]
  gobject_attr = rel_map["gobject_attr"]

  if hasattr(vcard, vcard_attr):
    for item in getattr(vcard, vcard_attr + "_list"):
      if item.type_param in rel_map["rel_map"]:
        rel = rel_map["rel_map"][item.type_param]
      else:
        rel = rel_map["rel_map"][None]

      uitem = unicode(item.value)

      # do we need to check the rel here too?
      matches = filter(
        lambda a: getattr(a, rel_map["gobject"]["attr"]) == uitem,
        getattr(gcontact, gobject_attr))

      if not len(matches):
        print "%s added to %s: (%s)" % (
          vcard_attr, gcontact.title.text, ", ".join(uitem.split("\n")))

        getattr(gcontact, gobject_attr).append(
          rel_map["gobject"]["class"](None, rel, uitem))
        return 1
  return 0

def update_cards(vcards, gd_client):
  query = gdata.contacts.service.ContactsQuery()
  query.max_results = 500 # is this acceptable?

  feed = gd_client.GetContactsFeed(query.ToUri())

  for (name, vcard) in vcards.items():
    gcontact = filter(lambda c: c.title.text == name, feed.entry)

    # I've no idea what I should really do here
    if len(gcontact) > 1:
      print >> sys.stderr, "%s: Ambiguous entry (by name)" % name
      continue

    if len(gcontact) < 1:
      gcontact = gdata.contacts.ContactEntry(title=atom.Title(text=name))

      # fill in the important bits
      for map_item in VOBJECT_VDATA_COMPLEX_REL_MAP:
        merge_object_with_ref(gcontact, vcard, map_item)

      merge_notes(gcontact, vcard)
      merge_org(gcontact, vcard)

      try:
        gd_client.CreateContact(gcontact)
      except gdata.service.RequestError, re:
        print >> sys.stderr, "Error: When processing '%s' google said: %d: %s" % (
          name, re.message["status"], re.message["reason"] )

    else:
      # only let goolge know what's going on if we actually changed a
      # record...
      changed = 0
      for map_item in VOBJECT_VDATA_COMPLEX_REL_MAP:
        changed += merge_object_with_ref(gcontact[0], vcard, map_item)

      # organisation and notes
      changed += merge_notes(gcontact[0], vcard) \
          + merge_org(gcontact[0], vcard)

      if changed > 0:
        try:
          gd_client.UpdateContact(gcontact[0].GetEditLink().href, gcontact[0])
        except gdata.service.RequestError, re:
          print >> sys.stderr, "Error: When processing '%s' google said: %d: %s" % (
            name, re.message["status"], re.message["reason"] )

def main(argv):
  if len(argv) < 3:
    print >> sys.stderr, "username password [vcard files...]"
    exit(1)

  gd_client = login(argv[0], argv[1])

  vcards = dict()
  for card in argv[2:]:
    fcard = open(card, "r")
    try:
      for vcard in vobject.readComponents(fcard):
        name = vcard.fn.value
        vcards[name] = vcard
    except Exception, v:
      print >> sys.stderr, "Warning, %s: %s" % (card, v)
      fcard.close()
      continue
    fcard.close()

  update_cards(vcards, gd_client)

def login(username, password):
  gd_client = gdata.contacts.service.ContactsService()
  gd_client.email = username
  gd_client.password = password
  gd_client.source = "none-vcardgmail-" + __VERSION__
  gd_client.accountType = "HOSTED_OR_GOOGLE"

  try:
    gd_client.ProgrammaticLogin()
  except gdata.service.BadAuthentication:
    print >> sys.stderr, "Authentication error (check username/password)."
    exit(1)

  return gd_client

if __name__ == "__main__":
  main(sys.argv[1:])