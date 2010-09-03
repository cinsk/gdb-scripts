#!/usr/bin/env python

# $Id$

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
import os
import subprocess
import atexit
import base64
import time

HEXDUMP_PATH="/usr/bin/hexdump"
ICONV_PATH="/usr/bin/iconv"

DEBUG=True

def error(message):
    sys.stderr.write("error: %s\n" % message)

def debug(message):
    if DEBUG:
        sys.stderr.write("debug: %s\n" % message)


class TmpFile(object):
    """A temporary file wrapper

This is a simple wrapper class for similar to os.tmpnam() with
automatic file creation.   Since os.tmpnam() has a security hole, but
GDB dump command creates its own file, so we cannot use Python tempfile
module.

   tmp = TmpFile()
   ...
   fd = open(tmp.name(), "w");
   ...
   
A temporary file createed once TmpFile object is created, then removed
automatically when the object is out of reference.   To handle the exception,
all temporary file names are recorded, then TmpFile.unlinkall() is registered
via atexit.register()."""
    TEMPLATE="/tmp/gdb-%s"
    filelist = dict()
    
    @staticmethod
    def AddFile(filename):
        """Add given filename into the local dictionary"""
        TmpFile.filelist[filename] = True

    @staticmethod
    def unlink(filename):
        """Unlink(remove) given filename, ignore any exception"""
        try:
            os.unlink(filename)
            del TmpFile.filelist[filename]
        except:
            pass

    @staticmethod
    def unlinkall():
        """Unlink(remove) all files created via TmpFile.

This method is good for atexit.register()."""
        #print "TmpFile.unlinkall()!"
        for f in TmpFile.filelist:
            TmpFile.unlink(f)
            
    def __init__(self, create=True):
        self.filename = None
        if create:
            self.create()

    def __del__(self):
        self.delete()
        
    def create(self):
        if self.filename != None:
            self.delete()
            
        tries = 0
        while True:
            sid = base64.b64encode("%s" % time.time()).replace("=", "_")
            filename = TmpFile.TEMPLATE % sid
            if not os.access(filename, os.F_OK):
                fd = open(filename, "w")
                fd.close()
                self.filename = filename
                break
            tries += 1
        #print "TmpFile.create(%s)" % self.filename

    def delete(self):
        #print "TmpFile.delete(%s)" % self.filename
        TmpFile.unlink(self.filename)
        self.filename = None

    def name(self):
        return self.filename
    
atexit.register(TmpFile.unlinkall)


class GdbDumpRunner(gdb.Command):
    """Wrapper for gdb.Command to make easy to make a new GDB command.

The __init__() accepts the same arguments as that of gdb.Command.

This class is for the GDB command that accept a symbol or memory
location for the data, then executes shell command to display the
data.

You need to inherit new class from this class, then override its
method.  For a simple shell command, overriding commandline() and
usage() methods are enough.  See the source code of HexDumpCommand,
HexDumpValueCommand, and HexdumpMemoryCommand for more.

If you need sofiscated handling of shell command, you may need to
override its parse_arguments() and execute() method.  See the source
code of IconvCommand, IconvValueCommand, and IconvMemoryCommand.

Internally, when a user defined command is executed, GdbDumpRunner's
invoke() is called.  Then, invoke() calls its parse_arguments() method
to parse the argument that passed to the GDB command.  The default
behavior of invoke() is to create a temporary file that has the data,
then call its execute() method.  The execute() method then calls its
commandline() method to get the shell command line argument, executes
the shell command, then print its output."""

    def __init__(self, name, cmdclass, completer = -1, prefix = False):
        gdb.Command.__init__(self, name, cmdclass, completer, prefix)
        self.completer = completer
        
    def commandline(self, filename, exec_args):
        """Returns the shell command line, in the form of a list of arguments.

By default, it returns an empty list.  You may need to override this
method.""" 
        return []

    def usage(self):
        """Prints the usage information in case of wrong/invalid arguments.

By default, it returns an empty string.  You may need to override this
method."""
        return ""

    def parse_arguments(self, args):
        """separate GDB dump arguments from arguments for execute() method.

Note that the return value should be (dump_arguments, exec_arguments).
Both members should be in string type.  By default, the argument to
this method should go to dump_arguments, and exec_arguments will be an
empty string."""
        return (args, "")
    
    def execute(self, filename, exec_args):
        """execute(filename, exec_args) -- Execute a shell command.

'filename' holds the filename that has the data GDB provides,
'exec_args' holds the command line arguments for the shell command in
string.

You may need to override this method if you want sofiscated shell
executing."""
        cmdline = self.commandline(filename, exec_args)
        debug("cmd: %s" % repr(cmdline))
        p = subprocess.Popen(cmdline,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = p.communicate()
        status = p.wait()

        sys.stdout.write(out)
        if err != "":
            sys.stdout.write(err)
        debug("exit status: %d" % status)
        return True
    
    def gdb_dump(self, filename, args):
        """gdb_dump(filename, args) -- Wrapper for the GDB dump command

'filename' is the output filename for the GDB dump command, 'args' is
a string that is passed to the GDB dump command."""
        
        if self.completer == gdb.COMPLETE_SYMBOL:
            cmd = "dump binary value %s %s" % (filename, args)
        elif self.completer == gdb.COMPLETE_LOCATION:
            cmd = "dump binary memory %s %s" % (filename, args)
        else:
            raise RuntimeError("completer class is not SYMBOL nor LOCATION")
        debug("executing GDB %s" % cmd)
        gdb.execute(cmd)
            
    def invoke(self, args, from_tty):
        """A callback for gdb.Command"""
        tmp = TmpFile()
        try:
            (dump_args, exec_args) = self.parse_arguments(args)
            self.gdb_dump(tmp.name(), dump_args)
            if not self.execute(tmp.name(), exec_args):
                print self.usage()
        except RuntimeError as e:
            print e
        except:
            sys.stderr.write("error: an exception occurred during excution")
            raise
            print self.usage()
        finally:
            sys.stdout.flush()
            del tmp


class HexdumpCommand(GdbDumpRunner):
    def __init__(self):
        GdbDumpRunner.__init__(self, "hexdump", gdb.COMMAND_DATA,
                               gdb.COMPLETE_NONE, True)

class HexdumpValueCommand(GdbDumpRunner):
    def __init__(self):
        GdbDumpRunner.__init__(self, "hexdump value", gdb.COMMAND_DATA,
                               gdb.COMPLETE_SYMBOL)

    def commandline(self, filename, exec_args):
        return [HEXDUMP_PATH, "-C", filename]

    def usage(self):
        return "usage: hexdump value EXPR"

class HexdumpMemoryCommand(GdbDumpRunner):
    def __init__(self):
        GdbDumpRunner.__init__(self, "hexdump memory", gdb.COMMAND_DATA,
                               gdb.COMPLETE_SYMBOL)

    def commandline(self, filename, exec_args):
        return [HEXDUMP_PATH, "-C", filename]

    def usage(self):
        return "usage: hexdump memory START_ADDR END_ADDR"


class IconvCommand(GdbDumpRunner):
    def __init__(self):
        GdbDumpRunner.__init__(self, "iconv", gdb.COMMAND_DATA, 0, True)

    @staticmethod
    def set_encoding(encoding = None):
        defenc = sys.getdefaultencoding().upper()
        if encoding == None:
            encoding = locale.getlocale()[1]
            
        if defenc != encoding and \
           defenc.find(encoding.upper()) < 0 and \
           encoding.upper().find(defenc) < 0:
            reload(sys)
            sys.setdefaultencoding(encoding)
            debug("Default encoding is changed to: %s" % encoding)
        else:
            debug("Default encoding is %s" % defenc)


class IconvEncodingCommand(gdb.Command):
    def __init__(self):
        # iconv value VALUE TO-ENCODING FROM-ENCODING...
        gdb.Command.__init__(self, "iconv encoding", gdb.COMMAND_STATUS,
                             gdb.COMPLETE_NONE, "iconv")

    def invoke(self, args, from_tty):
        argv = args.split()
        print "argv: ", argv
        if len(argv) == 0:
            print sys.getdefaultencoding()
        elif len(argv) == 1:
            try:
                IconvCommand.set_encoding(argv[0])
            except LookupError:
                sys.stderr.write("Unknown encoding: %s" % argv[0])


class IconvDumpRunner(GdbDumpRunner):
    def __init__(self, name, cmdclass,
                 completer = gdb.COMPLETE_NONE, prefix = False):
        GdbDumpRunner.__init__(self, name, cmdclass, completer, prefix)
    def format_error(self, msg):
        """Beautify the error message from the iconv(1)"""
        # Mostly, the error message from the iconv(1) will look like:
        #   /usr/bin/iconv: illegal input sequence at position 4

        # I don't want to be verbose.  Thus, accepting only the first line.
        pos = msg.find("\n")
        if pos > 0:
            msg = msg[:pos]
            
        pos = msg.find(":")
        if pos < 0:
            return msg
        else:
            return msg[pos + 1:]
        
    def execute(self, filename, exec_args):
        args = exec_args.split()
        to_enc = sys.getdefaultencoding()
        from_encs = args
        
        width = max(map(len, from_encs))
        for enc in from_encs:
            p = subprocess.Popen([ICONV_PATH,
                                  "-t", to_enc, "-f", enc, filename],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            (out, err) = p.communicate()
            status = p.wait()

            try:
                sys.stdout.write("%*s: " % (width, enc))
                #print "out: ", out
                sys.stdout.write("|%s|\n" % out)
            except TypeError as e:
                sys.stdout.write("\n")
                error("TypeError: %s" % e.args)
                error("Try to change the default encoding via 'iconv encoding'")

            if err != "":
                sys.stdout.write("\t%s\n" % self.format_error(err))
        return True


class IconvValueCommand(IconvDumpRunner):
    def __init__(self):
        # iconv value VALUE ENCODING...
        IconvDumpRunner.__init__(self, "iconv value", gdb.COMMAND_DATA,
                                 gdb.COMPLETE_SYMBOL, "iconv")
    def parse_arguments(self, args):
        # The first one is the symbol that needs to be passed GDB dump,
        # and the rest should be passed to execute() method
        (dump_args, dummy, exec_args) =  args.partition(' ')
        return (dump_args.strip(), exec_args.strip())

class IconvMemoryCommand(IconvDumpRunner):
    def __init__(self):
        # iconv value VALUE ENCODING...
        IconvDumpRunner.__init__(self, "iconv memory", gdb.COMMAND_DATA,
                                 gdb.COMPLETE_LOCATION, "iconv")
    def parse_arguments(self, args):
        # The first one is the symbol that needs to be passed GDB dump,
        # and the rest should be passed to execute() method
        args = args.strip()
        (args1, dummy, args2) =  args.partition(' ')
        mem_start = args1.strip()
        (args1, dummy, args2) =  args2.strip().partition(' ')
        mem_end = args1.strip()

        return ("%s %s" % (mem_start, mem_end), args2.strip())


class XmllintCommand(GdbDumpRunner):
    def __init__(self):
        GdbDumpRunner.__init__(self, "xmllint", gdb.COMMAND_DATA, 0, True)
        
class XmllintValueCommand(GdbDumpRunner):
    def __init__(self):
        GdbDumpRunner.__init__(self, "xmllint value", gdb.COMMAND_DATA,
                               gdb.COMPLETE_SYMBOL, "xmllint")

    def commandline(self, filename, exec_args):
        return [HEXDUMP_PATH, "-C", filename]

    def usage(self):
        return "usage: hexdump value EXPR"

hd = HexdumpCommand()
HexdumpValueCommand()
HexdumpMemoryCommand()

IconvCommand.set_encoding()
IconvCommand()
IconvValueCommand()
IconvMemoryCommand()
IconvEncodingCommand()
