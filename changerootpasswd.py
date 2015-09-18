#!/usr/bin/env bash
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 www.jd.com
#
# File: changerootpasswd.sh
# Author: xuriwuyun <xuriwuyun@gmail.com>
# Created: 11/19/2014 15:36:21
# Last_modified: 09/18/2015 13:53:10

import six
import sys
import random
import crypt

try:
    import guestfs
except Exception as e:
    raise Exception( "libguestfs is not installed (%s)" % e)



forceTCG = False


def force_tcg(force=True):
    """Prevent libguestfs trying to use KVM acceleration

    It is a good idea to call this if it is known that
    KVM is not desired, even if technically available.
    """

    global forceTCG
    forceTCG = force


class VFSGuestFS(object):

    """This class implements a VFS module that uses the libguestfs APIs
    to access the disk image. The disk image is never mapped into
    the host filesystem, thus avoiding any potential for symlink
    attacks from the guest filesystem.
    """
    def __init__(self, imgfile, imgfmt='raw', partition=-1):
        self.imgfile = imgfile
        self.imgfmt = imgfmt
        self.partition = partition

        self.handle = None

    def inspect_capabilities(self):
        """Determines whether guestfs is well configured."""
        try:
            g = guestfs.GuestFS()
            g.add_drive("/dev/null")  # sic
            g.launch()
        except Exception as e:
            raise Exception("libguestfs installed but not usable (%s)" % e)

        return self

    def setup_os(self):
        if self.partition == -1:
            self.setup_os_inspect()
        else:
            self.setup_os_static()

    def setup_os_static(self):
        print "Mount guest OS image %(imgfile)s partition %(part)s"%\
                {'imgfile': self.imgfile, 'part': str(self.partition)}

        if self.partition:
            self.handle.mount_options("", "/dev/sda%d" % self.partition, "/")
        else:
            self.handle.mount_options("", "/dev/sda", "/")

    def setup_os_inspect(self):
        print("Inspecting guest OS image %s"% self.imgfile)
        roots = self.handle.inspect_os()

        if len(roots) == 0:
            raise Exception("No operating system found in %s" % self.imgfile)

        if len(roots) != 1:
            print("Multi-boot OS %(roots)s"% {'roots': str(roots)})
            raise Exception("Multi-boot operating system found in %s" %
                self.imgfile)

        self.setup_os_root(roots[0])

    def setup_os_root(self, root):
        print("Inspecting guest OS root filesystem %s"% root)
        mounts = self.handle.inspect_get_mountpoints(root)

        if len(mounts) == 0:
            raise Exception("No mount points found in %(root)s of %(imgfile)s" %
                {'root': root, 'imgfile': self.imgfile})

        # the root directory must be mounted first
        mounts.sort(key=lambda mount: mount[0])

        root_mounted = False
        for mount in mounts:
            print("Mounting %(dev)s at %(dir)s"%
                      {'dev': mount[1], 'dir': mount[0]})
            try:
                self.handle.mount_options("", mount[1], mount[0])
                root_mounted = True
            except RuntimeError as e:
                msg = "Error mounting %(device)s to %(dir)s in image"\
                        " %(imgfile)s with libguestfs (%(e)s)" % \
                      {'imgfile': self.imgfile, 'device': mount[1],
                       'dir': mount[0], 'e': e}
                if root_mounted:
                    print(msg)
                else:
                    raise Exception(msg)

    def setup(self):
        print("Setting up appliance for %(imgfile)s %(imgfmt)s"%
                  {'imgfile': self.imgfile, 'imgfmt': self.imgfmt})
        try:
            self.handle = guestfs.GuestFS(python_return_dict=False, close_on_exit=False)
        except TypeError as e:
            if ('close_on_exit' in six.text_type(e) or
                'python_return_dict' in six.text_type(e)):
                # NOTE(russellb) In case we're not using a version of
                # libguestfs new enough to support parameters close_on_exit
                # and python_return_dict which were added in libguestfs 1.20.
                self.handle = guestfs.GuestFS()
            else:
                raise

        try:
            self.handle.add_drive_opts(self.imgfile, format=self.imgfmt)
            self.handle.launch()

            self.setup_os()

            self.handle.aug_init("/", 0)
        except RuntimeError as e:
            # explicitly teardown instead of implicit close()
            # to prevent orphaned VMs in cases when an implicit
            # close() is not enough
            self.teardown()
            raise Exception("Error mounting %(imgfile)s with libguestfs (%(e)s)" %
                {'imgfile': self.imgfile, 'e': e})
        except Exception:
            # explicitly teardown instead of implicit close()
            # to prevent orphaned VMs in cases when an implicit
            # close() is not enough
            self.teardown()
            raise

    def teardown(self):
        print("Tearing down appliance")

        try:
            try:
                self.handle.aug_close()
            except RuntimeError as e:
                print("Failed to close augeas %s"% e)

            try:
                self.handle.shutdown()
            except AttributeError:
                # Older libguestfs versions haven't an explicit shutdown
                pass
            except RuntimeError as e:
                print("Failed to shutdown appliance %s"% e)

            try:
                self.handle.close()
            except AttributeError:
                # Older libguestfs versions haven't an explicit close
                pass
            except RuntimeError as e:
                print("Failed to close guest handle %s"% e)
        finally:
            # dereference object and implicitly close()
            self.handle = None

    @staticmethod
    def _canonicalize_path(path):
        if path[0] != '/':
            return '/' + path
        return path

    def make_path(self, path):
        print("Make directory path=%s"% path)
        path = self._canonicalize_path(path)
        self.handle.mkdir_p(path)

    def command(self, cmd):
        cmd = cmd.split()
        print 'cmd: ', cmd
        self.handle.command(cmd)

    def append_file(self, path, content):
        print("Append file path=%s"% path)
        path = self._canonicalize_path(path)
        self.handle.write_append(path, content)

    def replace_file(self, path, content):
        print("Replace file path=%s"% path)
        path = self._canonicalize_path(path)
        self.handle.write(path, content)

    def read_file(self, path):
        print("Read file path=%s"% path)
        path = self._canonicalize_path(path)
        return self.handle.read_file(path)

    def has_file(self, path):
        print("Has file path=%s"% path)
        path = self._canonicalize_path(path)
        try:
            self.handle.stat(path)
            return True
        except RuntimeError:
            return False

    def set_permissions(self, path, mode):
        print("Set permissions path=%(path)s mode=%(mode)s"%
                  {'path': path, 'mode': mode})
        path = self._canonicalize_path(path)
        self.handle.chmod(mode, path)

    def set_ownership(self, path, user, group):
        print("Set ownership path=%(path)s "
                  "user=%(user)s group=%(group)s"%
                  {'path': path, 'user': user, 'group': group})
        path = self._canonicalize_path(path)
        uid = -1
        gid = -1

        if user is not None:
            uid = int(self.handle.aug_get(
                    "/files/etc/passwd/" + user + "/uid"))
        if group is not None:
            gid = int(self.handle.aug_get(
                    "/files/etc/group/" + group + "/gid"))

        print("chown uid=%(uid)d gid=%(gid)s"% {'uid': uid, 'gid': gid})
        self.handle.chown(uid, gid, path)


def _generate_salt():
    salt_set = ('abcdefghijklmnopqrstuvwxyz'
                'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                '0123456789./')
    salt = 16 * ' '
    return ''.join([random.choice(salt_set) for c in salt])

def encrypted_passwd(admin_passwd):
    algos = {'SHA-512': '$6$', 'SHA-256': '$5$', 'MD5': '$1$', 'DES': ''}

    salt = _generate_salt()

    # crypt() depends on the underlying libc, and may not support all
    # forms of hash. We try md5 first. If we get only 13 characters back,
    # then the underlying crypt() didn't understand the '$n$salt' magic,
    # so we fall back to DES.
    # md5 is the default because it's widely supported. Although the
    # local crypt() might support stronger SHA, the target instance
    # might not.
    encrypted_passwd = crypt.crypt(admin_passwd, algos['MD5'] + salt)
    if len(encrypted_passwd) == 13:
        encrypted_passwd = crypt.crypt(admin_passwd, algos['DES'] + salt)

    return encrypted_passwd


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print "USAGE: changerootpasswd.py image_file image_format password"
        exit(1)

    image_file = sys.argv[1]
    image_format = sys.argv[2]
    password = sys.argv[3]

    guest = VFSGuestFS(image_file, imgfmt=image_format)
    guest.setup()
    shadow_file = "/etc/shadow"
    shadow_data = guest.read_file(shadow_file)
    print shadow_data
    s_file = shadow_data.split("\n")

    passwd_encrypted = encrypted_passwd(password)
    command_str = r"sed -i -r /^root/s#root:([^:]+):(.*)#root:" + \
        passwd_encrypted + r":\2# " + shadow_file
    guest.command(command_str)

   # new_s_file = []
   # for entry in s_file:
   #     split_entry = entry.split(":")
   #     if split_entry[0] == "root":
   #         split_entry[1] = encrypted_passwd(password)

   #     new_s_file.append(':'.join(split_entry))

   # new_shadow_data = '\n'.join(new_s_file)
    new_shadow_data = guest.read_file(shadow_file)
    print new_shadow_data
    #guest.replace_file(shadow_file, new_shadow_data)
    guest.teardown()
