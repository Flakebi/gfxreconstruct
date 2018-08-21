#!/usr/bin/python3 -i
#
# Copyright (c) 2018 LunarG, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os,re,sys
from base_generator import *

class ApiCallAsciiConsumerDefinitionsGeneratorOptions(BaseGeneratorOptions):
    """Options for Vulkan API parameter processing C++ code generation"""
    def __init__(self,
                 blacklists = None,         # Path to JSON file listing apicalls and structs to ignore.
                 platformTypes = None,      # Path to JSON file listing platform (WIN32, X11, etc.) defined types.
                 filename = None,
                 directory = '.',
                 prefixText = '',
                 protectFile = False,
                 protectFeature = True):
        BaseGeneratorOptions.__init__(self, blacklists, platformTypes,
                                      filename, directory, prefixText,
                                      protectFile, protectFeature)

# ApiCallAsciiConsumerDefinitionsGenerator - subclass of BaseGenerator.
# Generates C++ member definitions for the VulkanAsciiConsumer class responsible for
# generating a textfile containing decoded Vulkan API call parameter data.
class ApiCallAsciiConsumerDefinitionsGenerator(BaseGenerator):
    """Generate API parameter processing C++ member definitions"""
    def __init__(self,
                 errFile = sys.stderr,
                 warnFile = sys.stderr,
                 diagFile = sys.stdout):
        BaseGenerator.__init__(self,
                               processCmds=True, processStructs=False, featureBreak=True,
                               errFile=errFile, warnFile=warnFile, diagFile=diagFile)

    #
    # Indicates that the current feature has C++ code to generate.
    def needFeatureGeneration(self):
        if self.featureCmdParams:
            return True
        return False

    #
    # Performs C++ code generation for the feature.
    def generateFeature(self):
        first = True
        for cmd in self.featureCmdParams:
            info = self.featureCmdParams[cmd]
            returnType = info[0]
            values = info[2]

            cmddef = '' if first else '\n'
            cmddef += self.makeConsumerFuncDecl(returnType, 'VulkanAsciiConsumer::Process_' + cmd, values) + '\n'
            cmddef += '{\n'
            cmddef += self.makeConsumerFuncBody(returnType, cmd, values)
            cmddef += '}'

            write(cmddef, file=self.outFile)
            first = False

    #
    # Return VulkanAsciiConsumer class member function definition.
    def makeConsumerFuncBody(self, returnType, name, values):
        body = '    fprintf(m_file, "%s\\n", "' + name + '");\n'
        return body