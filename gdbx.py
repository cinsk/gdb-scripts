#!/usr/bin/env python

# Some useful GDB command in python
# Copyright (C) 2010   Seong-Kook Shin <cinsky@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import sys
import locale
import gdb
import subprocess
import tempfile
import re

HEXDUMP_PATH="/usr/bin/hexdump"
ICONV_PATH="/usr/bin/iconv"
XMLLINT_PATH="/usr/bin/xmllint"

DEBUG=False

DEBUG_FD=sys.stderr
def error(message):
    sys.stderr.write("error: %s\n" % message)

def debug(message):
    if DEBUG:
        DEBUG_FD.write("debug: %s\n" % message)
        DEBUG_FD.flush()

def set_debug_file(pathname):
    global DEBUG_FD
    DEBUG_FD = open(pathname, "w")
    
def cmd_dump(filename, args, format="binary", type="value"):
    cmd = "dump %s %s %s %s" % (format, type, filename, args)
    debug("cmd_dump: executing '%s'..." % cmd )
    try:
        gdb.execute(cmd)
    except RuntimeError as e:
        error("%s" % e)
        #raise

def set_default_encoding(encoding = None):
    """set_default_encoding(encoding) - set the default character encoding

Set the default character encoding of the run-time.  If 'encoding' is not
provided, the current locale's character encoding is used by default.

If current locale's encoding is not set,  and 'encoding' is not provided,
the system encoding will not be changed.

On invalid encoding name, it returns False.  Otherwise returns True."""

    defenc = sys.getdefaultencoding().upper()
    debug("system default encoding: %s" % defenc)
    if encoding == None:
        encoding = locale.getlocale()[1]
        debug("locale encoding (LC_CTYPE): %s" % encoding)
        if encoding:
            encoding = encoding.upper()
        
    if encoding != None and defenc != encoding and \
       defenc.find(encoding) < 0 and encoding.find(defenc) < 0:
        # If the new encoding 'encoding' is different from the default
        # encoding 'defenc',
        reload(sys)
        try:
            sys.setdefaultencoding(encoding)
            debug("Default encoding is changed to: %s" % encoding)
        except LookupError as e:
            error("unrecoginized encoding, '%s'" % encoding)
            return False
    else:
        debug("Default encoding is %s" % defenc)

    
class GdbDumpParent(gdb.Command):
    def __init__(self, name, completer = -1, prefix = False):
        gdb.Command.__init__(self, name, gdb.COMMAND_DATA, completer, prefix)

    def parse_arguments(self, args):
        """parse the command arguments into two group; gdb dump
arguments and execute arguments.

GDB dump arguments is a string containing all arguments that will be
passed to the GDB 'dump' command.

Execute arguments is a string containing command line arguments that
will be used for the executing the shell command.  The exact command
line arguments are built via self.commandline()."""
        return (args, "")

    def commandline(self, filename, args):
        """commandline(filename, args) -- build the shell command line.

'filename' is the pathname of the file that contains the data, 'args'
is a string contains the arguments that is passed from user input.

The return value should be in either a string value or a list contains
one or more string values."""

        return []
    
    def execute(self, filename, args):
        cmdline = self.commandline(filename, args)
        if type(cmdline) != list:
            use_shell = True
        else:
            use_shell = False
        debug("type of cmdline: %s" % type(cmdline))
        debug("excuting %s (shell=%s)" % (cmdline, use_shell))
        p = subprocess.Popen(cmdline,
                             shell=use_shell,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = p.communicate()
        status = p.wait()

        sys.stdout.write(out)
        if err != "":
            sys.stdout.write(err)
        debug("exit status: %d" % status)
        return True

    def dump(self, filename, args):
        debug("Never reached here!!!")
        pass

    def on_execute_error(self):
        pass
    
    def invoke(self, args, from_tty):
        with tempfile.NamedTemporaryFile(prefix="gdb-") as tmp:
        #tmp = tempfile.NamedTemporaryFile(prefix="gdb-")
        #if True:
            try:
                (dump_args, exec_args) = self.parse_arguments(args)
                debug("dump_args: |%s|" % dump_args)
                debug("exec_args: |%s|" % exec_args)
                self.dump(tmp.name, dump_args)
                if not self.execute(tmp.name, exec_args):
                    self.on_execute_error()
            except RuntimeError as e:
                print e
            except:
                sys.stderr.write("error: an exception occurred during excution")
                raise
            
class GdbDumpValueParent(GdbDumpParent):
    def __init__(self, name, completer = -1, prefix = False):
        GdbDumpParent.__init__(self, name, completer, prefix)

    def dump(self, filename, args):
        cmd_dump(filename, args, format="binary", type="value")
        
class GdbDumpMemoryParent(GdbDumpParent):
    def __init__(self, name, completer = -1, prefix = False):
        GdbDumpParent.__init__(self, name, completer, prefix)

    def dump(self, filename, args):
        cmd_dump(filename, args, format="binary", type="memory")


class HexdumpCommand(gdb.Command):
    """Dump the given data using hexdump(1)"""
    def __init__(self):
        gdb.Command.__init__(self, "hexdump", gdb.COMMAND_DATA, -1, True)

class HexdumpImpl(object):
    def parse_argument(self, args):
        idx = args.find("##")
        if idx < 0:
            debug("hexdump impl parse args: |%s|, |%s|" % (args, ""))
            return (args, "")
        else:
            debug("hexdump impl parse args: |%s|, |%s|" % (args[:idx].strip(), args[idx+2:].strip()))
            return (args[:idx].strip(), args[idx+2:].strip())

    def commandline(self, filename, args):
        if args == "":
            return [HEXDUMP_PATH, "-C", filename]
        else:
            return "%s %s %s" % (HEXDUMP_PATH, args, filename)

    def complete(self, text, word):
        if text.find("##") < 0:
            return gdb.COMPLETE_SYMBOL
        else:
            return gdb.COMPELTE_NONE
        
class HexdumpValueCommand(GdbDumpValueParent):
    """Dump the value EXPR using hexdump(1)

usage: hexdump value EXPR [## OPTION...]

Dump the value, EXPR using hexdump(1).  If no OPTION is provided, '-C'
is assumed (canonnical hex+ASCII display).  If provided, OPTION is
passed to hexdump(1).  Note that you need '##' to separate EXPR from
OPTION.

For example, to dump the value, 'buffer' using hexdump(1) '-C':

    (gdb) hexdump value buffer

To dump the value, 'buffer' in one-byte octal display:

    (gdb) hexdump value buffer ## -b
"""
    def __init__(self):
        GdbDumpValueParent.__init__(self, "hexdump value", -1)
        self.impl = HexdumpImpl()
        
    def parse_arguments(self, args):
        return self.impl.parse_argument(args)
    
    def commandline(self, filename, args):
        return self.impl.commandline(filename, args)

    def complete(self, text, word):
        return self.impl.complete(text, word)
        
class HexdumpMemoryCommand(GdbDumpMemoryParent):
    """Dump the memory using hexdump(1)

usage: hexdump memory START_ADDR END_ADDR [## OPTION...]

Dump the memory from START_ADDR to END_ADDR using hexdump(1).  If no
OPTION is provided, '-C' is assumed (canonnical hex+ASCII display).
If provided, OPTION is passed to hexdump(1).  Note that you need '##'
to separate EXPR from OPTION.

For example, to dump the memory from 'buffer' (100 bytes) using
hexdump(1) '-C':

    (gdb) hexdump memory buffer ((char*)buffer+100)

To dump the value, 'buffer' in one-byte octal display:

    (gdb) hexdump memory buffer ((char*)buffer+100) ## -b
"""
    def __init__(self):
        GdbDumpMemoryParent.__init__(self, "hexdump memory", -1)
        self.impl = HexdumpImpl()
        
    def parse_arguments(self, args):
        return self.impl.parse_argument(args)
    
    def commandline(self, filename, args):
        return self.impl.commandline(filename, args)

    def complete(self, text, word):
        return self.impl.complete(text, word)
        
HexdumpCommand()
HexdumpValueCommand()
HexdumpMemoryCommand()


class IconvCommand(gdb.Command):
    """Check the character encoding of the data"""
    def __init__(self):
        gdb.Command.__init__(self, "iconv", gdb.COMMAND_DATA, -1, True)

class IconvEncodings(object):
    encodings = None
    replaces = "./:-()"
    
    @staticmethod
    def supported_encodings():
        ret = dict()
        try:
            p = subprocess.Popen([ICONV_PATH, "-l"], stdout=subprocess.PIPE)
            outbuf = p.communicate()[0]
            enclist = outbuf.split("\n")
            for enc in enclist:
                # 'enc' is something like "ANSI_X3.110-1983//"
                enc = enc.rstrip("/")
                alias = enc.lower()

                for repl in IconvEncodings.replaces:
                    alias = alias.replace(repl, "_")
                
                ret[alias] = enc
        except:
            print "error: cannot get supported encoding list"
            raise
        
        return ret

    def __init__(self):
        if IconvEncodings.encodings == None:
            IconvEncodings.encodings = IconvEncodings.supported_encodings()
            reload(sys)
            
    def name(self, alias):
        """Return the actual encoding name if exists, otherwise None"""
        alias = alias.lstrip("#")
        if IconvEncodings.encodings.has_key(alias):
            return IconvEncodings.encodings[alias]
        return None

    def complete(self, text, word):
        """Callback for auto completion, used in gdb.Command.complete()"""
        ret = list()

        debug("Encodings.complete(): text(%s) word(%s)" % (text, word))
        for a in IconvEncodings.encodings.iterkeys():
            #debug("    enc(%s)" % a)
            if a.find(word) == 0:
                ret.append(a)
        return ret
        
class IconvEncodingCommand(gdb.Command):
    """Set/get the current character encoding

usage: iconv encoding [ENCODING]

If ENCODING is not provided, this command shows the current system encoding.
If provided, this command set the current system encoding to ENCODING.

Once set, 'iconv value' and 'iconv memory' will try to convert the
given data into ENCODING.

Note that this changes the internal 'system default encoding' in
Python runtime."""
    
    def __init__(self):
        gdb.Command.__init__(self, "iconv encoding", gdb.COMMAND_DATA, -1)
        self.encodings = IconvEncodings()
        
    def invoke(self, arg, from_tty):
        arg = arg.strip()
        debug("arg: '%s'" % arg)
        if arg == "":
            print sys.getdefaultencoding()
        else:
            enc = self.encodings.name(arg)
            if enc != None:
                try:
                    sys.setdefaultencoding(enc)
                except LookupError as e:
                    error("encoding %s is not supported by Python" % enc)
            else:
                error("invalid encoding alias, %s." % arg)
    def complete(self, text, word):
        debug("iconv encoding complete: text(%s) word(%s)" % (text, word))
        return self.encodings.complete(text, word)
        
class IconvImpl(object):
    def __init__(self):
        self.re_encoding = re.compile(r"([ ]*(#[a-z0-9_]+))+")
        self.encodings = IconvEncodings()
        
    def partition(self, args):
        m = self.re_encoding.search(args)
        if m == None:
            return (args, "")
        else:
            idx = m.start()
            return (args[:idx], args[idx:])
            
    def format_error(self, errbuf):
        """Format iconv(1)-related error message

Currently, capture the only first line, removing iconv pathname"""
        (msg, dummy1, dummy2) = errbuf.partition("\n")
        idx = msg.find("iconv: ")
        if idx >= 0:
            return msg[idx:]
        
    def execute_iconv(self, filename, args):
        debug("execute_iconv('%s', '%s')" % (filename, args))
        encodings = list()
        for e in args.split():
            realname = self.encodings.name(e)
            if realname != None:
                debug("  target encoding: %s" % self.encodings.name(e))
                encodings.append(realname)
            else:
                error("unknown encoding alias %s, ignored" % e)
                
        target = sys.getdefaultencoding()

        width = max(map(len, encodings))

        sys.stdout.write("Target encoding is %s:\n" % target)
        
        for enc in encodings:
            cmdline = [ICONV_PATH, "-t", target, "-f", enc, filename]
            debug("cmdline: %s" % cmdline)
            p = subprocess.Popen(cmdline,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            (out, err) = p.communicate()
            status = p.wait()

            try:
                sys.stdout.write("%*s: " % (width, enc))
                sys.stdout.write("|%s|\n" % out)
            except TypeError as e:
                sys.stdout.write("\n")
                error("TypeError: %s" % e)
                error("Try to change the default encoding")
            if err != "":
                sys.stdout.write("\t%s\n" % self.format_error(err))
        return True
        
    def complete_any(self, text, word):
        try:
            prevchar = text[-(len(word) + 1)]
        except:
            prevchar = ""
        debug("complete: text(%s), word(%s), prev(%s)" % \
              (text, word, prevchar))
        if prevchar == "#":
            debug("complete for encoding...")
            return self.encodings.complete(text, word)
        else:
            debug("complete for symbol...")
            return gdb.COMPLETE_SYMBOL
        
class IconvValueCommand(GdbDumpValueParent, IconvImpl):
    """Check the encoding of the value EXPR.

usage: iconv memory EXPR ENCODING [ENCODING]...

Send a value EXPR to iconv(1) command to check the encoding of the
contents.  ENCODING is the source encoding of the memory region.  The
target encoding is controlled via 'iconv encoding' command.

If more than one ENCODING provided, iconv(1) is called several times
for each ENCODING.

ENCODING is an alias name that has a form '#name', where 'name' is
a encoding name except these:

  1. all capital letters are in lower-cases
  2. all non-alpha-numeric characters are substituted to the
     underline character('_').

For example, to use the character encoding 'ISO_8859-10:1992', the
ENCODING should be 'iso_8859_10_1992'.  Note that this command will
support auto-completion for the ENCODING.

For example, if you know want to make sure that the value 'buffer'
contains Korean character, but you don't know the exact encoding, you
may try following:

    (gdb) iconv memory buffer buffer+100 #euc_kr #cp949 #utf-8

Then it will try three times for the encoding 'EUC-KR', 'CP949', and
'UTF-8'."""
    # iconv value EXPR #ENCODING...
    
    def __init__(self):
        GdbDumpValueParent.__init__(self, "iconv value", -1)
        IconvImpl.__init__(self)

    def complete(self, text, word):
        return self.complete_any(text, word)

    def execute(self, filename, args):
        return self.execute_iconv(filename, args)
    
    def parse_arguments(self, args):
        return self.partition(args)
        
class IconvMemoryCommand(GdbDumpMemoryParent, IconvImpl):
    """Check the encoding of the memory.

usage: iconv memory START_ADDR END_ADDR ENCODING [ENCODING]...

Send a memory region to iconv(1) command to check the encoding of the
contents.  ENCODING is the source encoding of the memory region.  The
target encoding is controlled via 'iconv encoding' command.

If more than one ENCODING provided, iconv(1) is called several times
for each ENCODING.

ENCODING is an alias name that has a form '#name', where 'name' is
a encoding name except these:

  1. all capital letters are in lower-cases
  2. all non-alpha-numeric characters are substituted to the
     underline character('_').

For example, to use the character encoding 'ISO_8859-10:1992', the
ENCODING should be 'iso_8859_10_1992'.  Note that this command will
support auto-completion for the ENCODING.

For example, if you know want to make sure that the memory from
'buffer' to 'buffer+100' contains Korean character, but you don't know
the exact encoding, you may try following:

    (gdb) iconv memory buffer buffer+100 #euc_kr #cp949 #utf-8

Then it will try three times for the encoding 'EUC-KR', 'CP949', and
'UTF-8'."""
    # iconv value EXPR #ENCODING...
    
    def __init__(self):
        GdbDumpMemoryParent.__init__(self, "iconv memory", -1)
        IconvImpl.__init__(self)

    def complete(self, text, word):
        return self.complete_any(text, word)

    def execute(self, filename, args):
        return self.execute_iconv(filename, args)
    
    def parse_arguments(self, args):
        r = self.partition(args)
        debug("parse_argument: partition: %s" % repr(r))
        return r

class XmllintCommand(gdb.Command):
    """Check the XML using xmllint(1)"""
    def __init__(self):
        gdb.Command.__init__(self, "xmllint", gdb.COMMAND_DATA, -1, True)

class XmllintImpl(object):
    def complete(self, text, word):
        if text.find("##") < 0:
            return gdb.COMPLETE_SYMBOL
        else:
            return gdb.COMPLETE_NONE
        
    def partition(self, args):
        idx = args.rfind("##")
        if idx < 0:
            return (args, "")
        else:
            return (args[:idx].strip(), args[idx+2:].strip())

    def commandline(self, filename, args):
        # args is something like '--format --schema http://asdfadf --debug'
        return "%s %s %s" % (XMLLINT_PATH, args, filename)
        
class XmllintValueCommand(GdbDumpValueParent):
    """Check the value of an expression as a full XML document

Usage: xmllint value EXPR [## ARGUMENTS...]

Send the value of EXPR to xmllint(1) to check the validity.

ARGUMENTS is the additional arguments that will be passed to
xmllint(1).  If you use ARGUMENTS, make sure to separate them from
EXPR using '##'.

To validate 'xml_buffer', just use:

    (gdb) xmllint value xml_buffer
    
To validate 'xml_buffer' and to indent for human-readability:
    
    (gdb) xmllint value xml_buffer ## --format
"""
    def __init__(self):
        # xmllint value EXPR ## OPTIONS...
        
        GdbDumpValueParent.__init__(self, "xmllint value", -1)
        self.impl = XmllintImpl()
        
    def complete(self, text, word):
        debug("xmllint value complete: text(%s) word(%s)" % (text, word))
        return self.impl.complete(text, word)

    def parse_arguments(self, args):
        return self.impl.partition(args)

    def commandline(self, filename, args):
        return self.impl.commandline(filename, args)
    
class XmllintMemoryCommand(GdbDumpMemoryParent):
    """Check the contents of memory as a full XML document

Usage: xmllint memory START_ADDR END_ADDR [## ARGUMENTS...]

Send the memory from the address START_ADDR to the address END_ADDR to
xmllint(1) to check the validity.

ARGUMENTS is the additional arguments that will be passed to
xmllint(1).  If you use ARGUMENTS, make sure to separate them from
EXPR using '##'.

To validate a memory from 'xml_buffer' to plus 100 units:

    (gdb) xmllint memory xml_buffer xml_buffer+100

If 'xml_buffer' is not an array of character, you may need to cast it:

    (gdb) xmllint memory xml_buffer ((char*)xml_buffer)+100

To validate and to indent for human-readability:
    
    (gdb) xmllint value xml_buffer xml_buffer+100 ## --format
"""
    def __init__(self):
        # xmllint value EXPR ## OPTIONS...
        
        GdbDumpMemoryParent.__init__(self, "xmllint memory", -1)
        self.impl = XmllintImpl()
        
    def complete(self, text, word):
        debug("xmllint memory complete: text(%s) word(%s)" % (text, word))
        return self.impl.complete(text, word)

    def parse_arguments(self, args):
        return self.impl.partition(args)

    def commandline(self, filename, args):
        return self.impl.commandline(filename, args)
    

set_default_encoding()

IconvCommand()
IconvEncodingCommand()
IconvValueCommand()
IconvMemoryCommand()

XmllintCommand()
XmllintValueCommand()
XmllintMemoryCommand()

#set_debug_file("/dev/pts/13")
