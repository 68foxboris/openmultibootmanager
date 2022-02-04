#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function
#############################################################################
#
# Copyright (C) 2014 Impex-Sat Gmbh & Co.KG
# Written by Sandro Cavazzoni <sandro@skanetwork.com>
# All Rights Reserved.
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#############################################################################

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Sources.List import List

from Tools.Directories import fileExists

from OMBManagerCommon import OMB_MAIN_DIR, OMB_DATA_DIR, OMB_UPLOAD_DIR, OMB_TMP_DIR
from OMBManagerLocale import _

from enigma import eTimer

import os
from os import path
import glob
import struct
from Components.Console import Console
from Components.SystemInfo import BoxInfo

OMB_GETBOXTYPE = BoxInfo.getItem("model")
OMB_GETBRANDOEM = BoxInfo.getItem("brand")
OMB_GETIMAGEDISTRO = BoxInfo.getItem("distro")
OMB_GETIMAGEVERSION = BoxInfo.getItem("imageversion")
OMB_GETIMAGEFILESYSTEM = BoxInfo.getItem("imagefs") # needed
OMB_GETIMAGEFOLDER = BoxInfo.getItem("imagedir") # needed
OMB_GETMACHINEMTDKERNEL = BoxInfo.getItem("mtdkernel")
OMB_GETMACHINEKERNELFILE = BoxInfo.getItem("kernelfile") # needed
OMB_GETMACHINEMTDBOOT = BoxInfo.getItem("mtdbootfs")
OMB_GETMACHINEMTDROOT = BoxInfo.getItem("mtdrootfs")
OMB_GETMACHINEROOTFILE = BoxInfo.getItem("rootfile") # needed
OMB_GETMACHINEMKUBIFS = BoxInfo.getItem("mkubifs")
OMB_GETMACHINEUBINIZE = BoxInfo.getItem("ubinize")


class OMBManagerInstall(Screen):
	skin = """
			<screen position="360,150" size="560,400">
				<widget name="info"
						position="10,10"
						size="540,50"
						font="Regular;18"
						zPosition="1" />
				<widget source="list"
						render="Listbox"
						position="10,60"
						zPosition="1"
						size="540,330"
						scrollbarMode="showOnDemand"
						transparent="1" >

					<convert type="StringList" />
				</widget>
			</screen>"""

	def __init__(self, session, mount_point, upload_list):
		Screen.__init__(self, session)

		self.setTitle(_('openMultiboot Install'))

		self.session = session
		self.mount_point = mount_point

		self.esize = "128KiB"
		self.vid_offset = "2048"
		self.nandsim_parm = "first_id_byte=0x20 second_id_byte=0xac third_id_byte=0x00 fourth_id_byte=0x15"

		self['info'] = Label(_("Choose the image to install"))
		self["list"] = List(upload_list)
		self["actions"] = ActionMap(["SetupActions"],
		{
			"cancel": self.keyCancel,
			"ok": self.keyInstall
		})

	def keyCancel(self):
		self.close()

	def keyInstall(self):
		self.selected_image = self["list"].getCurrent()
		if not self.selected_image:
			return

		self.messagebox = self.session.open(MessageBox, _('Please wait while installation is in progress.\nThis operation may take a while.'), MessageBox.TYPE_INFO, enable_input=False)
		self.timer = eTimer()
		self.timer.callback.append(self.installPrepare)
		self.timer.start(100)
		self.error_timer = eTimer()
		self.error_timer.callback.append(self.showErrorCallback)

	def showErrorCallback(self):
		self.error_timer.stop()
		self.session.open(MessageBox, self.error_message, type=MessageBox.TYPE_ERROR)
		self.close()

	def showError(self, error_message):
		self.messagebox.close()
		self.error_message = error_message
		self.error_timer.start(100)

	def guessIdentifierName(self, selected_image):
		selected_image = selected_image.replace(' ', '_')
		prefix = self.mount_point + '/' + OMB_DATA_DIR + '/'
		if not os.path.exists(prefix + selected_image):
			return selected_image

		count = 1
		while os.path.exists(prefix + selected_image + '_' + str(count)):
			count += 1

		return selected_image + '_' + str(count)

	def installPrepare(self):
		self.timer.stop()

		selected_image = self.selected_image
		selected_image_identifier = self.guessIdentifierName(selected_image)

		source_file = self.mount_point + '/' + OMB_UPLOAD_DIR + '/' + selected_image + '.zip'
		target_folder = self.mount_point + '/' + OMB_DATA_DIR + '/' + selected_image_identifier
		kernel_target_folder = self.mount_point + '/' + OMB_DATA_DIR + '/.kernels'
		kernel_target_file = kernel_target_folder + '/' + selected_image_identifier + '.bin'

		if not os.path.exists(OMB_MAIN_DIR):
			try:
				os.makedirs(OMB_MAIN_DIR)
			except OSError as exception:
				self.showError(_("Cannot create main folder %s") % OMB_MAIN_DIR)
				return

		if not os.path.exists(kernel_target_folder):
			try:
				os.makedirs(kernel_target_folder)
			except OSError as exception:
				self.showError(_("Cannot create kernel folder %s") % kernel_target_folder)
				return

		if os.path.exists(target_folder):
			self.showError(_("The folder %s already exist") % target_folder)
			return

		try:
			os.makedirs(target_folder)
		except OSError as exception:
			self.showError(_("Cannot create folder %s") % target_folder)
			return

		tmp_folder = self.mount_point + '/' + OMB_TMP_DIR
		if os.path.exists(tmp_folder):
			Console().ePopen("rm -rf %s" % tmp_folder)
		try:
			os.makedirs(tmp_folder)
			os.makedirs(tmp_folder + '/ubi')
			os.makedirs(tmp_folder + '/jffs2')
		except OSError as exception:
			self.showError(_("Cannot create folder %s") % tmp_folder)
			return

		if os.system('unzip ' + source_file + ' -d ' + tmp_folder) != 0:
			self.showError(_("Cannot deflate image"))
			return

		nfifile = glob.glob('%s/*.nfi' % tmp_folder)
		tarxzfile = glob.glob('%s/*.rootfs.tar.xz' % tmp_folder)
		if nfifile:
			if not self.extractImageNFI(nfifile[0], tmp_folder):
				self.showError(_("Cannot extract nfi image"))
				return
			else:
				Console().ePopen("rm -f %s" % source_file)
				self.afterInstallImage(target_folder)
				self.messagebox.close()
				self.close()
		if tarxzfile:
			if os.system('/bin/tar' + ' xpJf %s -C %s' % (tarxzfile[0], target_folder)) != 0:
				if not os.path.exists(target_folder + "/usr/bin/enigma2"):
					self.showError(_("Error unpacking rootfs"))
					Console().ePopen("rm -rf %s" % tmp_folder)
				else:
					self.afterInstallImage(target_folder)
					Console().ePopen("rm -f %s" % source_file)
					Console().ePopen("rm -rf %s" % tmp_folder)
					self.messagebox.close()
					self.close(target_folder)
			else:
				self.showError(_("Error unpacking rootfs"))
				Console().ePopen("rm -rf %s" % tmp_folder)
		elif self.installImage(tmp_folder, target_folder, kernel_target_file, tmp_folder):
			Console().ePopen("rm -f %s" % source_file)
			Console().ePopen("rm -rf %s" % tmp_folder)
			self.messagebox.close()
			self.close(target_folder)
		else:
			Console().ePopen("rm -rf %s" % tmp_folder)

	def installImage(self, src_path, dst_path, kernel_dst_path, tmp_folder):
		if "ubi" in OMB_GETIMAGEFILESYSTEM:
			return self.installImageUBI(src_path, dst_path, kernel_dst_path, tmp_folder)
		elif "jffs2" in OMB_GETIMAGEFILESYSTEM:
			return self.installImageJFFS2(src_path, dst_path, kernel_dst_path, tmp_folder)
		elif "tar.bz2" in OMB_GETIMAGEFILESYSTEM:
			return self.installImageTARBZ2(src_path, dst_path, kernel_dst_path, tmp_folder)
		else:
			self.showError(_("Your STB doesn\'t seem supported"))
			return False

	def installImageTARBZ2(self, src_path, dst_path, kernel_dst_path, tmp_folder):
		base_path = src_path + '/' + OMB_GETIMAGEFOLDER
		rootfs_path = base_path + '/' + OMB_GETMACHINEROOTFILE
		kernel_path = base_path + '/' + OMB_GETMACHINEKERNELFILE

		if os.system('tar jxf %s -C %s' % (rootfs_path, dst_path)) != 0:
			self.showError(_("Error unpacking rootfs"))
			return False

		if os.path.exists(dst_path + '/usr/bin/enigma2'):
			if os.system('cp ' + kernel_path + ' ' + kernel_dst_path) != 0:
				self.showError(_("Error copying kernel"))
				return False

		self.dirtyHack(dst_path)

		return True

	def installImageJFFS2(self, src_path, dst_path, kernel_dst_path, tmp_folder):
		rc = True
		mtdfile = "/dev/mtdblock0"
		for i in range(0, 20):
			mtdfile = "/dev/mtdblock%d" % i
			if not os.path.exists(mtdfile):
				break

		base_path = src_path + '/' + OMB_GETIMAGEFOLDER
		rootfs_path = base_path + '/' + OMB_GETMACHINEROOTFILE
		kernel_path = base_path + '/' + OMB_GETMACHINEKERNELFILE
		jffs2_path = src_path + '/jffs2'

		if os.path.exists('/usr/bin/unjffs2'):
			if os.system("unjffs2 %s %s" % (rootfs_path, jffs2_path)) != 0:
				self.showError(_("Error unpacking rootfs"))
				rc = False

			if os.path.exists(jffs2_path + '/usr/bin/enigma2'):
				if os.system('cp -rp ' + jffs2_path + '/* ' + dst_path) != 0:
					self.showError(_("Error copying unpacked rootfs"))
					rc = False
				if os.system('cp ' + kernel_path + ' ' + kernel_dst_path) != 0:
					self.showError(_("Error copying kernel"))
					rc = False
		else:
			Console().ePopen("modprobe loop")
			Console().ePopen("modprobe mtdblock")
			Console().ePopen("modprobe block2mtd")
			Console().ePopen("mknod %s b 31 0" % mtdfile)
			Console().ePopen("losetup /dev/loop0 %s" % rootfs_path)
			Console().ePopen('echo "/dev/loop0,%s" > /sys/module/block2mtd/parameters/block2mtd' % self.esize)
			Console().ePopen("mount -t jffs2 %s %s" % (mtdfile, jffs2_path))

			if os.path.exists(jffs2_path + '/usr/bin/enigma2'):
				if os.system('cp -rp ' + jffs2_path + '/* ' + dst_path) != 0:
					self.showError(_("Error copying unpacked rootfs"))
					rc = False
				if os.system('cp ' + kernel_path + ' ' + kernel_dst_path) != 0:
					self.showError(_("Error copying kernel"))
					rc = False
			else:
				self.showError(_("Generic error in unpack process"))
				rc = False

			Console().ePopen("umount %s" % jffs2_path)
			Console().ePopen("rmmod block2mtd")
			Console().ePopen("rmmod mtdblock")
			Console().ePopen("rmmod loop")

		return rc

	def installImageUBI(self, src_path, dst_path, kernel_dst_path, tmp_folder):
		rc = True
		for i in range(0, 20):
			mtdfile = "/dev/mtd" + str(i)
			if os.path.exists(mtdfile) is False:
				break
		mtd = str(i)

		base_path = src_path + '/' + OMB_GETIMAGEFOLDER
		rootfs_path = base_path + '/' + OMB_GETMACHINEROOTFILE
		kernel_path = base_path + '/' + OMB_GETMACHINEKERNELFILE
		ubi_path = src_path + '/ubi'

		# This is idea from EGAMI Team to handle universal UBIFS unpacking - used only for INI-HDp model
		if OMB_GETBOXTYPE in ("xpeedlx3", "sezammarvel", "mbultra", "beyonwizt4", "atemionemesis"):
			if path.isdir("/usr/lib64"):
				ubifile = "/usr/lib64/enigma2/python/Plugins/Extensions/OpenMultiboot/ubi_reader/ubi_extract_files.pyo"
			else:
				ubifile = "/usr/lib/enigma2/python/Plugins/Extensions/OpenMultiboot/ubi_reader/ubi_extract_files.pyo"
			Console().ePopen("chmod 755 %s" % ubifile)
			Console().ePopen("python %s %s -o %s" % (ubifile, rootfs_path, ubi_path))
			Console().ePopen("cp -rp %s/rootfs/* %s" % (ubi_path, dst_path))
			Console().ePopen("chmod -R +x %s" % dst_path)
			Console().ePopen("rm -rf %s" % ubi_path)
			Console().ePopen("cp %s %s" % (kernel_path, kernel_dst_path))
			self.dirtyHack(dst_path)
			return True

		virtual_mtd = tmp_folder + '/virtual_mtd'
		Console().ePopen("modprobe nandsim cache_file=%s %s" % (virtual_mtd, self.nandsim_parm))
		if not os.path.exists('/dev/mtd' + mtd):
			Console().ePopen('rmmod nandsim')
			self.showError(_("Cannot create virtual MTD device"))
			return False

		if not os.path.exists('/dev/mtdblock' + mtd):
			Console().ePopen("dd if=%s of=/dev/mtd%s bs=2048" % (rootfs_path, mtd))
		else:
			Console().ePopen("dd if=%s of=/dev/mtdblock%s bs=2048" % (rootfs_path, mtd))
		Console().ePopen("ubiattach /dev/ubi_ctrl -m %s -O %s" % (mtd, self.vid_offset))
		Console().ePopen("mount -t ubifs ubi1_0 %s" % ubi_path)

		if os.path.exists(ubi_path + '/usr/bin/enigma2'):
			if os.system('cp -rp ' + ubi_path + '/* ' + dst_path) != 0:
				self.showError(_("Error copying unpacked rootfs"))
				rc = False
			if os.system('cp ' + kernel_path + ' ' + kernel_dst_path) != 0:
				self.showError(_("Error copying kernel"))
				rc = False
		else:
			self.showError(_("Generic error in unpack process"))
			rc = False

		Console().ePopen("umount %s" % ubi_path)
		Console().ePopen("ubidetach -m %s" % mtd)
		Console().ePopen("rmmod nandsim")

		self.dirtyHack(dst_path)

		self.afterInstallImage(dst_path)

		return rc

	# Based on nfi Extract by gutemine
	def extractImageNFI(self, nfifile, extractdir):
		nfidata = open(nfifile, 'r')
		header = nfidata.read(32)
		if header[:3] != 'NFI':
			print('Sorry, old NFI format deteced')
			nfidata.close()
			return False
		else:
			machine_type = header[4:4 + header[4:].find('\0')]
			if header[:4] == 'NFI3':
				machine_type = 'dm7020hdv2'

		print('Dreambox image type: %s' % machine_type)
		if machine_type in ('dm800', 'dm500hd', 'dm800se'):
			self.esize = '0x4000,0x200'
			self.vid_offset = '512'
			bs = 512
			bso = 528
		elif machine_type == 'dm7020hd':
			self.esize = '0x40000,0x1000'
			self.vid_offset = '4096'
			self.nandsim_parm = 'first_id_byte=0xec second_id_byte=0xd5 third_id_byte=0x51 fourth_id_byte=0xa6'
			bs = 4096
			bso = 4224
		elif machine_type == 'dm8000':
			self.esize = '0x20000,0x800'
			self.vid_offset = '512'
			bs = 2048
			bso = 2112
		else: # dm7020hdv2, dm500hdv2, dm800sev2
			self.esize = '0x20000,0x800'
			self.vid_offset = '2048'
			self.nandsim_parm = 'first_id_byte=0xec second_id_byte=0xd3 third_id_byte=0x51 fourth_id_byte=0x95'
			bs = 2048
			bso = 2112

		(total_size, ) = struct.unpack('!L', nfidata.read(4))
		print('Total image size: %s Bytes' % total_size)

		part = 0
		while nfidata.tell() < total_size:
			(size, ) = struct.unpack('!L', nfidata.read(4))
			print('Processing partition # %d size %d Bytes' % (part, size))
			output_names = {2: 'kernel.bin', 3: 'rootfs.bin'}
			if part not in output_names:
				nfidata.seek(size, 1)
				print('Skipping %d data...' % size)
			else:
				print('Extracting %s with %d blocksize...' % (output_names[part], bs))
				output_filename = extractdir + '/' + output_names[part]
				if os.path.exists(output_filename):
					os.remove(output_filename)
				output = open(output_filename, 'wb')
				if part == 2:
					output.write(nfidata.read(size))
				else:
					for sector in range(size / bso):
						d = nfidata.read(bso)
						output.write(d[:bs])
				output.close()
			part = part + 1

		nfidata.close()
		print('Extracting %s to %s Finished!' % (nfifile, extractdir))

		return True

	def dirtyHack(self, dst_path):
# WARNING: dirty hack by Meo
#
# In a perfect world all the images are perfect and do their work.
# But this is not a perfect world and we have to help OMB to
# prevent funny cases for non standard images.
# My apologies to Sandro for this bad code.
		try:
			for pyver in ["2.7", "3.9"]:
				if os.path.exists('/usr/lib/python' + pyver + '/boxbranding.so'):
					if not os.path.exists('/usr/lib/python' + pyver + '/boxbranding.so'):
						os.system("ln -s /usr/lib/enigma2/python/boxbranding.so /usr/lib/python' + pyver  + '/boxbranding.so")
					if os.path.exists(dst_path + '/usr/lib/python' + pyver + '/boxbranding.pyo'):
						os.system("cp /usr/lib/enigma2/python/boxbranding.so " + dst_path + "/usr/lib/python' + pyver  + '/boxbranding.so")
						os.system("rm -f " + dst_path + '/usr/lib/python' + pyver + '/boxbranding.pyo')
					if not os.path.exists(dst_path + "/usr/lib/python" + pyver + "/subprocess.pyo"):
						os.system("cp /usr/lib/python" + pyver + "/subprocess.pyo " + dst_path + "/usr/lib/python" + pyver + "/subprocess.pyo")
		except:
			pass
		try:
			for pyver in ["2.7", "3.9"]:
				if os.path.exists('/usr/lib64/python' + pyver + '/boxbranding.so'):
					if not os.path.exists('/usr/lib64/python' + pyver + '/boxbranding.so'):
						os.system("ln -s /usr/lib64/enigma2/python/boxbranding.so /usr/lib64/python' + pyver  + '/boxbranding.so")
					if os.path.exists(dst_path + '/usr/lib64/python' + pyver + '/boxbranding.pyo'):
						os.system("cp /usr/lib64/enigma2/python/boxbranding.so " + dst_path + "/usr/lib64/python' + pyver  + '/boxbranding.so")
						os.system("rm -f " + dst_path + '/usr/lib64/python' + pyver + '/boxbranding.pyo')
					if not os.path.exists(dst_path + "/usr/lib64/python" + pyver + "/subprocess.pyo"):
						os.system("cp /usr/lib64/python" + pyver + "/subprocess.pyo " + dst_path + "/usr/lib64/python" + pyver + "/subprocess.pyo")
		except:
			pass
# OpenMultiboot installed in the multiboot image. where the init will go ?
		if os.path.exists(dst_path + '/sbin/open_multiboot'):
			Console().ePopen("rm -f %s/sbin/open_multiboot" % dst_path)
			Console().ePopen("rm -f %s/sbin/open-multiboot-branding-helper.pyo" % dst_path)
			Console().ePopen("rm -f %s/etc/ipk-postinsts/*-OpenMultiboot" % dst_path)
# We can't create the init symlink because it will be overwrited by OpenMultiboot
			Console().ePopen("ln -sfn /sbin/init.sysvinit %s/sbin/open_multiboot" % dst_path)

	def afterInstallImage(self, dst_path):
		fix = False
		error = False
		file = dst_path + '/etc/init.d/volatile-media.sh'
		if os.path.exists(file):
			try:
				f = open(file, 'r')
				for line in f.readlines():
					if line.find('mountpoint -q "/media" || mount -t tmpfs -o size=64k tmpfs /media') > -1:
						fix = True
						break
				f.close()
			except:
				error = True
			if not fix and not error:
				import fileinput
				for line in fileinput.input(file, inplace=True):
					if 'mount -t tmpfs -o size=64k tmpfs /media' in line:
						print("mountpoint -q \"/media\" || mount -t tmpfs -o size=64k tmpfs /media")
					else:
						print(line.rstrip())
