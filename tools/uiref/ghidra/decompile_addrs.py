import json, os
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor
prog=currentProgram
OUT=os.environ.get("DEC_ADDRS_OUT","/home/builder/vmwork/opencode/decompile_addrs.json")
ADDRS=[int(x,16) for x in os.environ["DEC_ADDRS"].split(",")]
ifc=DecompInterface(); ifc.openProgram(prog); mon=ConsoleTaskMonitor()
fm=prog.getFunctionManager()
res_out={}
for a in ADDRS:
    ad=prog.getAddressFactory().getDefaultAddressSpace().getAddress(a)
    f=fm.getFunctionAt(ad)
    if f is None:
        res_out[hex(a)]={"status":"no-function"}; continue
    r=ifc.decompileFunction(f,120,mon)
    df=getattr(r,"decompiledFunction",None)
    if df is None:
        res_out[hex(a)]={"status":"decompile-failed"}; continue
    code=df.getC()
    res_out[hex(a)]={"status":"ok","function":f.getName(),"code":code}
    with open(os.path.join(os.path.dirname(OUT), "addr_"+hex(a)[2:]+".c"),"w") as fh: fh.write(code)
json.dump(res_out,open(OUT,"w"),indent=1)
print("ADDRS_OK",sum(1 for v in res_out.values() if v.get("status")=="ok"),"of",len(ADDRS))
