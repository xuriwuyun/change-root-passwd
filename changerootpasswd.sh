#!/usr/bin/env bash                                                             
# vim: tabstop=4 shiftwidth=4 softtabstop=4                                     
#                                                                               
# Copyright 2013 www.jd.com                                                     
#                                                                               
# File: changerootpasswd.sh                                                     
# Author: xuriwuyun <xuriwuyun@gmail.com>                                       
# Created: 11/19/2014 15:36:21                                                  
# Last_modified: 11/19/2014 15:45:46                                            
                                                                                
echo $#                                                                         
if [ $# -ne 2 ]                                                                 
then                                                                            
    echo USAGE: changerootpasswd image_file password                            
    exit 1                                                                      
fi                                                                              
                                                                                
image_format=`qemu-img info $1|grep 'file format'|awk '{print $3}'`             
                                                                                
python changerootpasswd.py $1 $image_format $2  
