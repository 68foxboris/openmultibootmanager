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

import sys
from Components.SystemInfo import BoxInfo

KEYS_FNC_MAP = {
	'machine_mtd_kernel': 'BoxInfo.getItem("mtdkernel")',
	'machine_kernel_file': 'BoxInfo.getItem("kernelfile")',
	'machine_mtd_boot': 'BoxInfo.getItem("mtdbootfs")',
	'machine_mtd_root': 'BoxInfo.getItem("mtdrootfs")',
	'machine_root_file': 'BoxInfo.getItem("rootfile")',
	'machine_mkubifs': 'BoxInfo.getItem("mkubifs")',
	'machine_ubinize': 'BoxInfo.getItem("ubinize")',
	'box_type': 'BoxInfo.getItem("model")',
	'brand_oem': 'BoxInfo.getItem("brand")',
	'image_version': 'BoxInfo.getItem("imageversion")',
	'image_build': 'BoxInfo.getItem("imagebuild")',
	'image_distro': 'BoxInfo.getItem("distro")',
	'image_folder': 'BoxInfo.getItem("imagedir")',
	'image_file_system': 'BoxInfo.getItem("imagefs")'
}


def print_help():
	print('Syntax:')
	print(sys.argv[0] + ' enigma2_dir key')
	print('')
	print('Valid keys:')
	for key in KEYS_FNC_MAP.keys():
		print(' * ' + key)
	print(' * all')


if len(sys.argv) != 3:
	print_help()
else:
	sys.path.insert(0, sys.argv[1])

	if not sys.argv[2] in KEYS_FNC_MAP and sys.argv[2] != 'all':
		print_help()
	else:
		if sys.argv[2] == 'all':
			for key in KEYS_FNC_MAP.keys():
				print(key + ' = ' + eval(KEYS_FNC_MAP[key]))
		else:
			print(eval(KEYS_FNC_MAP[sys.argv[2]]))
