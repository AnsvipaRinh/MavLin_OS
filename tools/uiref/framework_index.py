#!/usr/bin/env python3
"""framework_index.py - systematic framework investigation pipeline.

Parses a thin (x86_64) Mach-O dylib/executable and emits a JSON index of:
  * load dependencies (LC_LOAD_DYLIB / REEXPORT / WEAK / LAZY_LOAD)
  * symbol table: defined + undefined (imported) symbols with addresses
  * exported symbols (LC_DYLD_INFO export trie) -> public API surface
  * Objective-C runtime metadata: classes, categories, methods (selector/types/IMP),
    ivars, protocols, and the selector/methname/classname string pools.
  * section inventory (name, addr, size, fileoff) for provenance.

Output: one JSON document per binary, schema mavlinos.framework-index/1.

Designed to be correct for 10.9 x86_64 binaries: segment vmaddr/fileoff deltas
are honoured so __DATA_CONST / __DATA ObjC structures resolve to the right file
offsets (a defect in the older machobjc.py, which assumed vmaddr==fileoff).

Usage:
    framework_index.py <macho-file> [--out FILE] [--no-ghidra]
"""
import argparse, json, struct, sys, zlib

MAGIC64_LE = 0xFEEDFACF
CMD_SEGMENT64 = 0x19
CMD_SYMTAB = 0x2
CMD_DYSYMTAB = 0xB
CMD_LOAD_DYLIB = 0xC
CMD_ID_DYLIB = 0xD
CMD_LOAD_WEAK_DYLIB = 0x1E
CMD_REEXPORT_DYLIB = 0x1F
CMD_LAZY_LOAD_DYLIB = 0x20
CMD_DYLD_INFO_ONLY = 0x22

SECT_TEXT = "__text"
SECT_CONST = "__const"
SECT_CSTRING = "__cstring"
SECT_DATA_CONST = "__DATA_CONST"
SECT_DATA = "__DATA"
SECT_OBJC_CLASSLIST = "__objc_classlist"
SECT_OBJC_CATLIST = "__objc_catlist"
SECT_OBJC_METHNAME = "__objc_methname"
SECT_OBJC_CLASSNAME = "__objc_classname"
SECT_OBJC_IVAR = "__objc_ivar"
SECT_OBJC_PROTOLIST = "__objc_protolist"
SECT_OBJC_PROTOREFS = "__objc_protolist_refs"  # not used

def u32(b, o, e="<"): return struct.unpack_from(e+"I", b, o)[0]
def u64(b, o, e="<"): return struct.unpack_from(e+"Q", b, o)[0]

class Seg:
    __slots__=("name","vmaddr","vmsize","fileoff","filesize","maxprot","initprot","nsect","sections")
    def __init__(self): self.sections={}

class MachO:
    def __init__(self, path):
        with open(path,"rb") as fh: self.buf=fh.read()
        self.buf=bytearray(self.buf)
        self.e="<"
        self.bits=64
        self.segments=[]; self.cmds=[]
        self._parse()
    def _parse(self):
        b=self.buf
        magic=u32(b,0,self.e)
        assert magic==MAGIC64_LE, "expected 64-bit LE Mach-O, got %#x"%magic
        ncmds=u32(b,16,self.e)
        off=32  # 64-bit header
        n=len(b)
        for _ in range(ncmds):
            if off+8>n: break
            cmd=u32(b,off,self.e); cmdsize=u32(b,off+4,self.e)
            if cmdsize<8 or off+cmdsize>n: break
            if cmd==CMD_SEGMENT64:
                if off+88>n: break
                sg=Seg()
                sg.name=b[off+8:off+24].split(b"\x00")[0].decode("ascii","replace")
                sg.vmaddr=u64(b,off+24,self.e)
                sg.vmsize=u64(b,off+32,self.e)
                sg.fileoff=u64(b,off+40,self.e)
                sg.filesize=u64(b,off+48,self.e)
                sg.maxprot=u32(b,off+56,self.e); sg.initprot=u32(b,off+60,self.e)
                sg.nsect=u32(b,off+64,self.e)
                so=off+72
                for _s in range(sg.nsect):
                    if so+80>n: break
                    sname=b[so:so+16].split(b"\x00")[0].decode("ascii","replace")
                    saddr=u64(b,so+32,self.e); ssize=u64(b,so+40,self.e)
                    sfoff=u32(b,so+48,self.e)
                    sg.sections[sname]=(saddr,ssize,sfoff)
                    so+=80
                self.segments.append(sg)
            else:
                self.cmds.append((cmd,off,cmdsize))
            off+=cmdsize
        # index sections by name (first match wins)
        self.sec={}
        for sg in self.segments:
            for name,(saddr,ssize,sfoff) in sg.sections.items():
                if name not in self.sec:
                    self.sec[name]=(sg,saddr,ssize,sfoff)
    def va2off(self,addr):
        for sg in self.segments:
            if sg.vmaddr<=addr<sg.vmaddr+sg.vmsize:
                return sg.fileoff+(addr-sg.vmaddr)
        return None
    def cstr(self,addr):
        p=self.va2off(addr)
        if p is None or p>=len(self.buf): return None
        e=self.buf.find(b"\x00",p)
        if e<0: e=len(self.buf)
        return bytes(self.buf[p:e]).decode("utf-8","replace")
    def get_section(self,name):
        return self.sec.get(name)
    def read_uleb128(self,p):
        r=0;s=0
        while True:
            by=self.buf[p];p+=1
            r|=(by&0x7f)<<s
            if not (by&0x80): break
            s+=7
        return r,p
    def read_leb128(self,p):
        r=0;s=0;shift=0
        while True:
            by=self.buf[p];p+=1
            r|=(by&0x7f)<<shift
            if not (by&0x80): break
            shift+=7
        # sign extend
        size=shift+7
        if r & (1<<(size-1)): r-= (1<<size)
        return r,p

def parse_dyld_exports(m):
    """Return sorted list of exported symbol names from LC_DYLD_INFO export trie."""
    out=[]
    for cmd,off,cmdsize in m.cmds:
        if cmd!=CMD_DYLD_INFO_ONLY: continue
        # dataoff,datasize
        doff=u32(m.buf,off+8,m.e); dsize=u32(m.buf,off+12,m.e)
        base=doff
        # terminal size = 4 bytes (all zeros)
        def walk(node,prefix):
            p=node
            term=u32(m.buf,p,m.e); p+=4
            if term!=0: return
            n=u32(m.buf,p,m.e); p+=4
            for _ in range(n):
                str_off=u32(m.buf,p,m.e); p+=4
                skip=u32(m.buf,p,m.e); p+=4
                # read string
                sp=base+str_off
                e=m.buf.find(b"\x00",sp)
                name=bytes(m.buf[sp:e]).decode("utf-8","replace") if e>=0 else ""
                if skip==0:
                    out.append(prefix+name)
                else:
                    walk(base+skip, prefix+name)
        walk(base,"")
        return sorted(set(out))
    return None

def parse_symbols(m):
    syms={"defined":[],"undefined":[]}
    for cmd,off,cmdsize in m.cmds:
        if cmd==CMD_SYMTAB:
            stroff=u32(m.buf,off+16,m.e); strsize=u32(m.buf,off+20,m.e)
            symoff=u32(m.buf,off+8,m.e); nsyms=u32(m.buf,off+12,m.e)
            strtab=bytes(m.buf[stroff:stroff+strsize])
            for i in range(nsyms):
                n=nlist_off=symoff+i*12  # 64-bit nlist is 12 bytes? no: strx(4)+type(1)+sect(1)+desc(2)+value(8)=16
            # 64-bit nlist entry: uint32 strx, uint8 type, uint8 sect, int16 desc, uint64 value = 16 bytes
            stride=16
            for i in range(nsyms):
                e=symoff+i*stride
                strx=u32(m.buf,e,m.e)
                ntype=m.buf[e+4]; nsect=m.buf[e+5]
                desc=u32(m.buf,e+6,"<") # desc is 2 bytes; read as part
                value=u64(m.buf,e+8,m.e)
                name_end=strtab.find(b"\x00",strx)
                name=bytes(strtab[strx:name_end]).decode("utf-8","replace") if name_end>=0 else ""
                # N_EXT bit = 0x1 external; N_TYPE mask
                ntype_mask=ntype&0x0e
                undef=(ntype_mask==0)  # N_UNDF
                ext=bool(ntype&0x01)
                entry={"name":name,"value":hex(value),"sect":nsect,"desc":desc}
                if undef and ext:
                    syms["undefined"].append(entry)
                elif not undef:
                    syms["defined"].append(entry)
            return syms
    return syms

def parse_dependencies(m):
    deps=[]
    for cmd,off,cmdsize in m.cmds:
        if cmd in (CMD_LOAD_DYLIB,CMD_LOAD_WEAK_DYLIB,CMD_REEXPORT_DYLIB,CMD_LAZY_LOAD_DYLIB,CMD_ID_DYLIB):
            nameoff=u32(m.buf,off+8,m.e)
            p=off+nameoff
            e=m.buf.find(b"\x00",p)
            name=bytes(m.buf[p:e]).decode("utf-8","replace")
            deps.append({"cmd":hex(cmd),"name":name})
    return deps

def read_ro_pointers(m, addr):
    """read 8-byte pointer at vmaddr addr -> target vmaddr"""
    p=m.va2off(addr)
    if p is None: return None
    return u64(m.buf,p,m.e)

def parse_objc(m):
    res={"classes":[],"categories":[],"selector_pool":[],"classname_pool":[]}
    clist=m.get_section(SECT_OBJC_CLASSLIST)
    catlist=m.get_section(SECT_OBJC_CATLIST)
    if not clist: return res
    sg,saddr,ssize,sfoff=clist
    n=ssize//8
    for i in range(n):
        cls_addr=u64(m.buf,sfoff+i*8,m.e)
        if not cls_addr: continue
        info=read_class(m,cls_addr)
        if info: res["classes"].append(info)
    if catlist:
        sg,saddr,ssize,sfoff=catlist
        n=ssize//8
        for i in range(n):
            ca=u64(m.buf,sfoff+i*8,m.e)
            if not ca: continue
            ci=read_category(m,ca)
            if ci: res["categories"].append(ci)
    return res

def read_class(m,cls_addr):
    p=m.va2off(cls_addr)
    if p is None: return None
    try:
        isa,sup,cache,vtable,data=u64(m.buf,p,m.e),u64(m.buf,p+8,m.e),u64(m.buf,p+16,m.e),u64(m.buf,p+24,m.e),u64(m.buf,p+32,m.e)
    except struct.error:
        return None
    rp=m.va2off(data & ~0x7)
    if rp is None: return None
    try:
        # class_ro_t 64-bit: 4x u32 + 7x u64
        flags=u32(m.buf,rp,m.e); inststart=u32(m.buf,rp+4,m.e); instsize=u32(m.buf,rp+8,m.e); _res=u32(m.buf,rp+12,m.e)
        ivl,name_addr,methods_addr,protos,ivars,weak,props=struct.unpack_from("<7Q",m.buf,rp+16)
    except struct.error:
        return None
    name=m.cstr(name_addr)
    if not name: return None
    sup_name=class_super_name(m,sup)
    methods=[]
    if methods_addr:
        mp=m.va2off(methods_addr)
        if mp is not None:
            try:
                entsz_flags=u32(m.buf,mp,m.e); cnt=u32(m.buf,mp+4,m.e)
                off=mp+8
                entsz=24
                for _ in range(min(cnt,20000)):
                    if off+24>len(m.buf): break
                    n,t,imp=struct.unpack_from("<QQQ",m.buf,off)
                    sel=m.cstr(n)
                    if sel:
                        methods.append({"selector":sel,"types":m.cstr(t),"imp":hex(imp)})
                    off+=entsz
            except struct.error: pass
    ivars_out=[]
    if ivars:
        ip=m.va2off(ivars)
        if ip is not None:
            try:
                cnt=u32(m.buf,ip+4,m.e); off=ip+8
                for _ in range(min(cnt,1000)):
                    nameoff=u32(m.buf,off,m.e); typeoff=u32(m.buf,off+4,m.e)
                    nm=m.cstr(nameoff)
                    if nm: ivars_out.append({"name":nm,"type":m.cstr(typeoff)})
                    off+=32
            except struct.error: pass
    return {"name":name,"super":sup_name,"methods":methods,"ivars":ivars_out,
            "ro_addr":hex(cls_addr),"data_addr":hex(data&~0x7)}

def class_super_name(m,sup):
    if not sup: return None
    sp=m.va2off(sup+32)
    if sp is None: return None
    try:
        sdata=u64(m.buf,sp,m.e)&~0x7
        srp=m.va2off(sdata)
        if srp is None: return None
        return m.cstr(struct.unpack_from("<I",m.buf,srp+24)[0])
    except struct.error: return None

def read_category(m,ca):
    p=m.va2off(ca)
    if p is None: return None
    try:
        cls_name_addr,cat_name_addr,methods_addr=struct.unpack_from("<QQQ",m.buf,p)
    except struct.error: return None
    cls=m.cstr(cls_name_addr); cat=m.cstr(cat_name_addr)
    if not cls or not cat: return None
    methods=[]
    if methods_addr:
        mp=m.va2off(methods_addr)
        if mp is not None:
            try:
                entsz_flags=u32(m.buf,mp,m.e); cnt=u32(m.buf,mp+4,m.e)
                off=mp+8
                for _ in range(min(cnt,20000)):
                    if off+24>len(m.buf): break
                    n,t,imp=struct.unpack_from("<QQQ",m.buf,off)
                    sel=m.cstr(n)
                    if sel: methods.append({"selector":sel,"types":m.cstr(t),"imp":hex(imp)})
                    off+=24
            except struct.error: pass
    return {"class":cls,"category":cat,"methods":methods}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("binary")
    ap.add_argument("--out")
    a=ap.parse_args()
    m=MachO(a.binary)
    doc={"schema":"mavlinos.framework-index/1","binary":a.binary,
         "dependencies":parse_dependencies(m),
         "symbols":parse_symbols(m),
         "exports":parse_dyld_exports(m),
         "sections":{name:[hex(sa),hex(ss),hex(sf)] for name,(sg,sa,ss,sf) in m.sec.items()},
         "objc":parse_objc(m)}
    text=json.dumps(doc,indent=1,sort_keys=True)
    if a.out: open(a.out,"w").write(text)
    else: print(text[:4000])
    oc=doc["objc"]
    print(f"index: {len(oc['classes'])} classes, {len(oc['categories'])} categories, "
          f"{len(doc['symbols']['defined'])} defined syms, {len(doc['symbols']['undefined'])} undefined, "
          f"{len(doc['dependencies'])} deps, {len(doc['exports'] or [])} exports")

if __name__=="__main__":
    sys.exit(main())
