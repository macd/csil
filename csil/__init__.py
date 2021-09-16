##
## Copyright (c) 2021 Don MacMillen
## 
## This file is part of csil
## (see https://github.com/macd/csil).
## 
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
## 
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
## 
## You should have received a copy of the GNU General Public License
## along with this program. If not, see <http://www.gnu.org/licenses/>.
## 
"""
Don MacMillen Aug. 2021
"""
name = "csil"

__version__ = "0.0.1"
   
from .csil import CDesign
from .utils import plt_csv, iselect
from .splat import splat_one, splat, dump_script
