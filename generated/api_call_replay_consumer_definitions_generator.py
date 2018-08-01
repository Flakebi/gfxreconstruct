#!/usr/bin/python3 -i
#
# Copyright (c) 2013-2016 The Khronos Group Inc.
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
from generator import *
from common_codegen import GetFeatureProtect

# CGeneratorOptions - subclass of GeneratorOptions.
#
# Adds options used by COutputGenerator objects during C language header
# generation.
#
# Additional members
#   prefixText - list of strings to prefix generated header with
#     (usually a copyright statement + calling convention macros).
#   protectFile - True if multiple inclusion protection should be
#     generated (based on the filename) around the entire header.
#   protectFeature - True if #ifndef..#endif protection should be
#     generated around a feature interface in the header file.
#   genFuncPointers - True if function pointer typedefs should be
#     generated
#   protectProto - If conditional protection should be generated
#     around prototype declarations, set to either '#ifdef'
#     to require opt-in (#ifdef protectProtoStr) or '#ifndef'
#     to require opt-out (#ifndef protectProtoStr). Otherwise
#     set to None.
#   protectProtoStr - #ifdef/#ifndef symbol to use around prototype
#     declarations, if protectProto is set
#   apicall - string to use for the function declaration prefix,
#     such as APICALL on Windows.
#   apientry - string to use for the calling convention macro,
#     in typedefs, such as APIENTRY.
#   apientryp - string to use for the calling convention macro
#     in function pointer typedefs, such as APIENTRYP.
#   indentFuncProto - True if prototype declarations should put each
#     parameter on a separate line
#   indentFuncPointer - True if typedefed function pointers should put each
#     parameter on a separate line
#   alignFuncParam - if nonzero and parameters are being put on a
#     separate line, align parameter names at the specified column
class APICallReplayConsumerDefinitionsGeneratorOptions(GeneratorOptions):
    """Represents options during C interface generation for headers"""
    def __init__(self,
                 filename = None,
                 directory = '.',
                 apiname = None,
                 profile = None,
                 versions = '.*',
                 emitversions = '.*',
                 defaultExtensions = None,
                 addExtensions = None,
                 removeExtensions = None,
                 emitExtensions = None,
                 sortProcedure = regSortFeatures,
                 prefixText = "",
                 genFuncPointers = True,
                 protectFile = True,
                 protectFeature = True,
                 protectProto = None,
                 protectProtoStr = None,
                 apicall = '',
                 apientry = '',
                 apientryp = '',
                 indentFuncProto = True,
                 indentFuncPointer = False,
                 alignFuncParam = 0):
        GeneratorOptions.__init__(self, filename, directory, apiname, profile,
                                  versions, emitversions, defaultExtensions,
                                  addExtensions, removeExtensions,
                                  emitExtensions, sortProcedure)
        self.prefixText      = prefixText
        self.genFuncPointers = genFuncPointers
        self.protectFile     = protectFile
        self.protectFeature  = protectFeature
        self.protectProto    = protectProto
        self.protectProtoStr = protectProtoStr
        self.apicall         = apicall
        self.apientry        = apientry
        self.apientryp       = apientryp
        self.indentFuncProto = indentFuncProto
        self.indentFuncPointer = indentFuncPointer
        self.alignFuncParam  = alignFuncParam

# COutputGenerator - subclass of OutputGenerator.
# Generates C-language API interfaces.
#
# ---- methods ----
# COutputGenerator(errFile, warnFile, diagFile) - args as for
#   OutputGenerator. Defines additional internal state.
# ---- methods overriding base class ----
# beginFile(genOpts)
# endFile()
# beginFeature(interface, emit)
# endFeature()
# genType(typeinfo,name)
# genStruct(typeinfo,name)
# genGroup(groupinfo,name)
# genEnum(enuminfo, name)
# genCmd(cmdinfo)
class APICallReplayConsumerDefinitionsOutputGenerator(OutputGenerator):
    """Generate specified API interfaces in a specific style, such as a C header"""
    # This is an ordered list of sections in the header file.
    ALL_SECTIONS = ['command']
    # These API calls should not be processed by the code generator.  They require special layer specific implementations.
    APICALL_BLACKLIST = ['vkGetInstanceProcAddr',
                         'vkGetDeviceProcAddr',
                         'vkEnumerateInstanceLayerProperties',
                         'vkEnumerateDeviceLayerProperties',
                         'vkEnumerateInstanceExtensionProperties',
                         'vkEnumerateDeviceExtensionProperties',
                         'vkEnumerateInstanceVersion']
    # These types represent pointers to non-Vulkan objects that were written as 64-bit address IDs.
    EXTERNAL_OBJECT_TYPES = ['void', 'Void', 'AHardwareBuffer']
    def __init__(self,
                 errFile = sys.stderr,
                 warnFile = sys.stderr,
                 diagFile = sys.stdout):
        OutputGenerator.__init__(self, errFile, warnFile, diagFile)
        # Internal state - accumulators for different inner block text
        self.sections = dict([(section, []) for section in self.ALL_SECTIONS])
        # Typenames
        self.structNames = set()                          # Set of Vulkan struct typenames
        self.handleTypes = set()                          # Set of handle type names
    #
    def beginFile(self, genOpts):
        OutputGenerator.beginFile(self, genOpts)
        # C-specific
        #
        # Multiple inclusion protection & C++ wrappers.
        if (genOpts.protectFile and self.genOpts.filename):
            headerSym = re.sub('\.h', '_h',
                               os.path.basename(self.genOpts.filename)).upper()
            write('#ifndef', headerSym, file=self.outFile)
            write('#define', headerSym, file=self.outFile)
        #
        # User-supplied prefix text, if any (list of strings)
        if (genOpts.prefixText):
            for s in genOpts.prefixText:
                write(s, file=self.outFile)
    def endFile(self):
        # C-specific
        # Finish C++ wrapper and multiple inclusion protection
        if (self.genOpts.protectFile and self.genOpts.filename):
            self.newline()
            write('#endif', file=self.outFile)
        # Finish processing in superclass
        OutputGenerator.endFile(self)
    def beginFeature(self, interface, emit):
        # Start processing in superclass
        OutputGenerator.beginFeature(self, interface, emit)
        # C-specific
        # Accumulate includes, defines, types, enums, function pointer typedefs,
        # end function prototypes separately for this feature. They're only
        # printed in endFeature().
        self.sections = dict([(section, []) for section in self.ALL_SECTIONS])
        self.featureExtraProtect = GetFeatureProtect(interface)
    def endFeature(self):
        # C-specific
        # Actually write the interface to the output file.
        if (self.emit and self.sections['command']):
            self.newline()
            if (self.genOpts.protectFeature):
                write('#ifndef', self.featureName, file=self.outFile)
            # If type declarations are needed by other features based on
            # this one, it may be necessary to suppress the ExtraProtect,
            # or move it below the 'for section...' loop.
            if (self.featureExtraProtect != None):
                write('#ifdef', self.featureExtraProtect, file=self.outFile)
            if (self.genOpts.protectProto):
                write(self.genOpts.protectProto,
                        self.genOpts.protectProtoStr, file=self.outFile)
            write('\n'.join(self.sections['command']), end='', file=self.outFile)
            if (self.genOpts.protectProto):
                write('#endif', file=self.outFile)
            if (self.featureExtraProtect != None):
                write('#endif /*', self.featureExtraProtect, '*/', file=self.outFile)
            if (self.genOpts.protectFeature):
                write('#endif /*', self.featureName, '*/', file=self.outFile)
        # Finish processing in superclass
        OutputGenerator.endFeature(self)
    #
    # Append a definition to the specified section
    def appendSection(self, section, text):
        # self.sections[section].append('SECTION: ' + section + '\n')
        self.sections[section].append(text)
    #
    # Type generation
    def genType(self, typeinfo, name, alias):
        OutputGenerator.genType(self, typeinfo, name, alias)
        typeElem = typeinfo.elem
        # If the type is a struct type, traverse the imbedded <member> tags
        # generating a structure. Otherwise, emit the tag text.
        category = typeElem.get('category')
        if (category == 'struct' or category == 'union'):
            self.structNames.add(name)
            self.genStruct(typeinfo, name, alias)
        elif (category == 'handle'):
            self.handleTypes.add(name)
    #
    # Struct (e.g. C "struct" type) generation.
    # This is a special case of the <type> tag where the contents are
    # interpreted as a set of <member> tags instead of freeform C
    # C type declarations. The <member> tags are just like <param>
    # tags - they are a declaration of a struct or union member.
    # Only simple member declarations are supported (no nested
    # structs etc.)
    def genStruct(self, typeinfo, typeName, alias):
        OutputGenerator.genStruct(self, typeinfo, typeName, alias)
    #
    # Group (e.g. C "enum" type) generation.
    # These are concatenated together with other types.
    def genGroup(self, groupinfo, groupName, alias):
        OutputGenerator.genGroup(self, groupinfo, groupName, alias)
    # Enumerant generation
    # <enum> tags may specify their values in several ways, but are usually
    # just integers.
    def genEnum(self, enuminfo, name, alias):
        OutputGenerator.genEnum(self, enuminfo, name, alias)
    #
    # Command generation
    def genCmd(self, cmdinfo, name, alias):
        OutputGenerator.genCmd(self, cmdinfo, name, alias)
        #
        if not name in self.APICALL_BLACKLIST:
            cmddef = self.makeConsumerDecl(cmdinfo.elem, 'VulkanReplayConsumer::Process_') + '\n'
            cmddef += self.makeConsumerBody(cmdinfo.elem, cmdinfo.elem.findall('param'))
            self.appendSection('command', cmddef)
    #
    # makeConsumerDecl - return VulkanConsumer class member declaration
    # cmd - Element containing a <command> tag
    # prefix - String to prepend to command name
    def makeConsumerDecl(self, cmd, prefix = ''):
        """Generate VulkanConsumer class member declaration for <command> Element"""
        returnType = None
        proto = cmd.find('proto')
        params = cmd.findall('param')
        # Begin accumulating prototype and typedef strings
        pdecl = self.genOpts.apicall
        #
        # Insert the function return type/name.
        # For prototypes, add APIENTRY macro before the name.
        # Done by walking the tree for <proto> element by element.
        # etree has elem.text followed by (elem[i], elem[i].tail)
        #   for each child element and any following text
        # Leading text
        pdecl += noneStr(proto.text)
        # For each child element, if it's a <name> wrap in appropriate
        # declaration. Otherwise append its contents and tail contents.
        for elem in proto:
            text = noneStr(elem.text)
            tail = noneStr(elem.tail)
            if (elem.tag == 'name'):
                pdecl += prefix + self.makeProtoName(text, tail)
            elif (elem.tag == 'type'):
                typename = text + tail
                if (typename.strip() != 'void'):
                    returnType = typename
                pdecl += 'void '
            else:
                pdecl += text + tail
        # Now add the parameter declaration list. Concatenate all
        # the text from a <param> node without the tags. No tree
        # walking required since all tags are ignored.
        # Uses: self.indentFuncProto
        # self.indentFuncPointer
        # self.alignFuncParam
        # Might be able to doubly-nest the joins, e.g.
        #   ','.join(('_'.join([l[i] for i in range(0,len(l))])
        n = len(params)
        # Indented parameters
        if (n > 0) or returnType:
            indentdecl = '(\n'
            if returnType:
                # We do not currently have to worry about pointer return values, but may need to do so in the future.
                if '*' in returnType:
                    print('WARNING: Pointer return values are not currently supported ' + typename)
                paramdecl = self.makeConsumerParamDecl(returnType, 'returnValue', self.genOpts.alignFuncParam)
                indentdecl += paramdecl + ',\n'
            for i in range(0,n):
                paramtype = self.makeDecoderParamType(params[i], 'const ', '&')
                entry = params[i].find('name')
                paramname = noneStr(entry.text) + noneStr(entry.tail)
                paramdecl = self.makeConsumerParamDecl(paramtype, paramname, self.genOpts.alignFuncParam)
                if (i < n - 1):
                    paramdecl += ',\n'
                else:
                    paramdecl += ')'
                indentdecl += paramdecl
        else:
            indentdecl = '()'
        # Non-indented parameters
        paramdecl = '('
        if n > 0:
            for i in range(0,n):
                paramdecl += ''.join([t for t in params[i].itertext()])
                if (i < n - 1):
                    paramdecl += ', '
        paramdecl += ")";
        return pdecl + indentdecl
    #
    # indent - indent all lines in a string
    # value - String to indent
    # spaces - Number of spaces to indent
    def indent(self, value, spaces):
        prefix = ' ' * spaces
        return '\n'.join([prefix + v for v in value.split('\n')])
    #
    # makeConsumerParamDecl - return a string which is an indented, formatted
    # declaration for a parameter.
    # paramtype - Parameter type to format
    # paramname - Parameter name to format
    # aligncol - if non-zero, attempt to align the nested <name> element
    #   at this column
    def makeConsumerParamDecl(self, paramtype, paramname, aligncol):
        paramdecl = '    ' + paramtype
        # Alignment code from makeCParamDecl
        if (aligncol > 0):
            self.logMsg('diag', 'Aligning parameter return to column', aligncol)
            # Align at specified column, if possible
            paramdecl = paramdecl.rstrip()
            oldLen = len(paramdecl)
            # This works around a problem where very long type names -
            # longer than the alignment column - would run into the tail
            # text.
            paramdecl = paramdecl.ljust(aligncol-1) + ' '
            newLen = len(paramdecl)
            self.logMsg('diag', 'Adjust length of parameter decl from', oldLen, 'to', newLen, ':', paramdecl)
        paramdecl += paramname.split('[')[0]
        return paramdecl
    #
    # Check if the parameter is a function pointer
    def isFunctionPtr(self, typename):
        result = False
        if typename[:4] == 'PFN_':
            result = True
        return result
    #
    # Check if the parameter is a pointer
    def getPointerCount(self, param):
        result = 0
        paramtype = param.find('type')
        if (paramtype.tail is not None) and ('*' in paramtype.tail):
            result = paramtype.tail.count('*')
        return result
    #
    # Retrieve the value of the len tag
    def getArrayLen(self, param):
        result = None
        len = param.attrib.get('len')
        if len:
            # Check for a string or array of strings
            if 'null-terminated' in len:
                # Strings are ignored, but string arrays are checked for a length value.
                # For string arrays, 'len' can look like 'count,null-terminated', indicating that we have an array of null terminated
                # strings.  We strip the null-terminated substring from the 'len' field and only return the parameter specifying the string count.
                if len != 'null-terminated':
                    result = len.split(',')[0]
            else:
                result = len
            if result:
                result = str(result).replace('::', '->')
        else:
            # Check for a static array
            paramname = param.find('name')
            if (paramname.tail is not None) and ('[' in paramname.tail):
                start = paramname.tail.find('[') + 1
                end = paramname.tail.find(']')
                result = paramname.tail[start:end]
        return result
    #
    # Check if the parameter is a static array
    def isStaticArray(self, param):
        result = False
        paramname = param.find('name')
        if (paramname.tail is not None) and ('[' in paramname.tail):
            result = True
        return result
    #
    # Determine if a pointer parameter is an input parameter
    def isInputPointer(self, paramtype):
        # TODO: Need to determine if this is sufficient (eg. this was generally true for GLES, but some extensions
        #       did not adhere to this pattern of 'const = input, non-const = output'; may be a similar issue for Vulkan).
        return True if 'const' in paramtype else False
    #
    # Determine if a pointer parameter is an in/out array length
    def isArrayLen(self, paramname, params):
        for param in params:
            if paramname == self.getArrayLen(param):
                return True
        return False
    #
    # 
    #
    # makeDecoderParamType - return a typename for a decoded paramater, which may can be the original type
    #   wrapped in a decoder class.
    # param - Element (<param> or <member>) to format
    # wrapprefix - prefix to add to wrapped types (eg. 'const')
    # wrapsuffix - suffix to add to wrapped types (eg. '&')
    def makeDecoderParamType(self, param, wrapprefix = '', wrapsuffix = ''):
        typename = noneStr(param.find('type').text)
        count = self.getPointerCount(param)

        if count > 0:
            # We currently only expect the '*' count to be greater than one for the char** case
            if (count > 1) and (typename != 'char') and (not typename in self.EXTERNAL_OBJECT_TYPES):
                print('WARNING: Processing a multi-dimensional array that is not an array of strings ({})'.format(typename + ('*' * count)))
            if typename in self.structNames:
                typename = wrapprefix + 'StructPointerDecoder<Decoded_{}>'.format(typename) + wrapsuffix
            elif typename == 'char':
                if count > 1:
                    typename = wrapprefix + 'StringArrayDecoder' + wrapsuffix
                else:
                    typename = wrapprefix + 'StringDecoder' + wrapsuffix
            elif typename == 'void':
                if self.getArrayLen(param):
                    # If this was an array it was encoded as an array of bytes.
                    typename = wrapprefix + 'PointerDecoder<uint8_t>' + wrapsuffix
                elif count > 1:
                    # If this was a pointer to a pointer to an unknown object, it was encoded as a pointer to a 64-bit address value.
                    typename = wrapprefix + 'PointerDecoder<uint64_t>' + wrapsuffix
                else:
                    # If this was a pointer to an unknown object, it was encoded as a 64-bit address value.
                    typename = 'uint64_t'
            elif typename in self.handleTypes:
                # Handles are encoded as a 64-bit ID value.
                typename = wrapprefix + 'PointerDecoder<HandleId>' + wrapsuffix
            else:
                typename = wrapprefix + 'PointerDecoder<{}>'.format(typename) + wrapsuffix
        elif self.isStaticArray(param):
            if typename in self.structNames:
                typename = wrapprefix + 'StructPointerDecoder<Decoded_{}>'.format(typename) + wrapsuffix
            else:
                typename = wrapprefix + 'PointerDecoder<{}>'.format(typename) + wrapsuffix
        elif self.isFunctionPtr(typename):
            # Function pointers are encoded as a 64-bit address value.
            typename = 'uint64_t'
        elif typename in self.handleTypes:
            # Handles are encoded as a 64-bit ID value.
            typename = 'HandleId'
        elif typename in self.structNames:
            typename = wrapprefix + 'Decoded_{}'.format(typename) + wrapsuffix

        return typename
    #
    # makeBodyExpressions - 
    # name - the command name
    # params - 
    def makeBodyExpressions(self, name, params):
        # For array lengths that are stored in pointers, this will map the original parameter name
        # to the temporary parameter name that was created to store the value to be provided to the Vulkan API call.
        arraylengths = dict()

        args = []       # List of arguments to the API call.
        preexpr = []    # Variable declarations for handle mappings, temporary output allocations, and input pointers.
        postexpr = []   # Expressions to add new handles to the handle map and delete temporary allocations.

        for param in params:
            basetype = noneStr(param.find('type').text)   # Undecorated typename
            count = self.getPointerCount(param)
            cdecl = self.makeCParamDecl(param, 0)

            tokens = cdecl.strip().split(' ')
            paramtype = ' '.join(tokens[:-1])
            paramname = tokens[-1]

            isstaticarray = self.isStaticArray(param)

            if (count > 0) or isstaticarray:
                isinput = self.isInputPointer(paramtype)
                if isstaticarray:
                    # Need to convert from array syntax to pointer syntax
                    count = 1;
                    paramname = paramname.split('[')[0]
                    paramtype += '*'

                argname = 'in_' + paramname if isinput else 'out_' + paramname
                args.append(argname)

                expr = '{} {} = '.format(paramtype, argname)

                arraylen = self.getArrayLen(param)
                if arraylen:
                    lenname = arraylen
                    if arraylen in arraylengths:
                        # Array lengths with pointer types are received by the consumer as PointerDecoder<T> objects, so
                        # an intermediate value of type T is created to hold the value that will be provided to the Vulkan
                        # API call.  The 'arraylengths' dictionary contains a mapping of the original parameter name to the
                        # intermediate value name.  For this case, we need to use the intermediate value for array allocations.
                        lenname = arraylengths[arraylen] if arraylen in arraylengths else arraylen
                    elif '->' in arraylen:
                        # Some counts are members of an allocate info struct.  Similar to the above PointerDecoder<T> case,
                        # Pointers to structures are received in a StructPointerDecoder<T> object and an intermediate value is
                        # created to store the pointer encapsulated by the object.  This case also requires using the intermediate
                        # value to access the array length.  Prepending 'in_' to the 'arraylen' value is currently sufficient to
                        # handle this case.
                        lenname = 'in_' + lenname

                if isinput:
                    if basetype == 'void' and not arraylen:
                        # If this was an array with the 'void*' type, it was encoded as an array of bytes.
                        # If not (this case), it is a pointer to an unknown object type that was encoded as a uint64_t ID value.
                        # If possible, we will map the ID to an object previously created during replay.  Otherwise, we will
                        # need to report a warning that we may have a case that replay cannot handle.
                        # TODO: Handle mapped memory pointer case.
                        print("WARNING: Generating replay code for function {} with an unrecognized void* parameter.".format(name))
                        expr += 'nullptr;'
                    elif basetype == 'VkAllocationCallbacks':
                        # The replay consumer needs to override the allocation callbacks used by the captured application.
                        expr += 'GetAllocationCallbacks({});'.format(paramname)
                    elif basetype in self.handleTypes:
                        # We received an array of 64-bit integer IDs from the decoder.
                        # We now need to allocate memory to hold handles, which we map from the IDs.
                        expr = expr.replace('const', '').lstrip() + '{}.IsNull() ? nullptr : AllocateArray<{}>({});'.format(paramname, basetype, lenname)
                        preexpr.append(expr)
                        expr = 'MapHandles<{basetype}>({}.GetPointer(), {}, {}, &VulkanObjectMapper::Map{basetype});'.format(paramname, argname, lenname, basetype=basetype)
                        postexpr.append('FreeArray<{}>(&{});'.format(basetype, argname))
                    else:
                        expr += 'reinterpret_cast<{}>({}.GetPointer());'.format(paramtype, paramname)
                else:
                    if arraylen:
                        if basetype == 'void':
                            expr = 'uint8_t* {} = {}.IsNull() ? nullptr : AllocateArray<uint8_t>({});'.format(argname, paramname, lenname)
                            postexpr.append('FreeArray<uint8_t>(&{});'.format(argname))
                        else:
                            expr += '{}.IsNull() ? nullptr : AllocateArray<{}>({});'.format(paramname, basetype, lenname)
                            if basetype in self.handleTypes:
                                # Add mappings for the newly created handles
                                postexpr.append('AddHandles<{basetype}>({}.GetPointer(), {}, {}, &VulkanObjectMapper::Add{basetype});'.format(paramname, argname, lenname, basetype=basetype))
                            postexpr.append('FreeArray<{}>(&{});'.format(basetype, argname))
                    else:
                        if basetype == 'void':
                            # TODO: Handle mapped memory pointer case.
                            print("WARNING: Generating replay code for function {} with an unrecognized void* parameter.".format(name))
                            outval = 'out_{}_value'.format(paramname)
                            preexpr.append('void{} {} = nullptr;'.format('*' * (count - 1), outval))
                            expr += '&{};'.format(outval)
                        else:
                            outval = 'out_{}_value'.format(paramname)
                            if self.isArrayLen(paramname, params):
                                # If this is an array length, it is an in/out parameter and we need to assign the input value.
                                preexpr.append('{basetype} {} = {paramname}.IsNull() ? static_cast<{basetype}>(0) : *({paramname}.GetPointer());'.format(outval, basetype = basetype, paramname = paramname))
                                # Need to store the name of the intermediate value for use with allocating the array associated with this length.
                                arraylengths[paramname] = outval
                            elif basetype in self.structNames:
                                preexpr.append('{basetype} {} = {{}};'.format(outval, basetype = basetype))
                            else:
                                preexpr.append('{basetype} {} = static_cast<{basetype}>(0);'.format(outval, basetype = basetype))
                            expr += '&{};'.format(outval)
                            if basetype in self.handleTypes:
                                # Add mapping for the newly created handle
                                postexpr.append('AddHandles<{basetype}>({}.GetPointer(), {}, 1, &VulkanObjectMapper::Add{basetype});'.format(paramname, argname, basetype=basetype))
                preexpr.append(expr)
            elif basetype in self.handleTypes:
                # Handles need to be mapped.
                argname = 'in_' + paramname
                args.append(argname)
                expr = '{} {} = '.format(paramtype, argname)
                expr += 'object_mapper_.Map{}({});'.format(basetype, paramname)
                preexpr.append(expr)
            elif self.isFunctionPtr(basetype):
                # Function pointers are encoded as a 64-bit address value.
                # TODO: Check for cases that need to be handled.
                print("WARNING: Generating replay code for a function {} with a {} parameter that is undefined.".format(name, basetype))
            else:
                # Only need to append the parameter name to the args list; no other expressions are necessary.
                args.append(paramname)
        return args, preexpr, postexpr
    #
    # makeConsumerBody - return VulkanConsumer class member definition
    # cmd - Element containing a <command> tag
    def makeConsumerBody(self, cmd, params):
        proto = cmd.find('proto')
        protoname = noneStr(proto.find('name').text)

        args, preexpr, postexpr = self.makeBodyExpressions(protoname, params)

        body = '{\n'
        if preexpr:
            body += '\n'.join(['    ' + val for val in preexpr])
            body += '\n'
            body += '\n'
        body += '    {}({});\n'.format(protoname, ', '.join(args))
        if postexpr:
            body += '\n'
            body += '\n'.join(['    ' + val for val in postexpr])
            body += '\n'
        body += '}\n'

        return body
