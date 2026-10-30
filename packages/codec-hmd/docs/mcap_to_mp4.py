#!/usr/bin/env python3
"""Convert foxglove.CompressedVideo (H.265) tracks in a Visio MCAP to MP4 with
CORRECT timing: each frame's PTS comes from the message's own capture timestamp
(VFR), NOT an assumed constant frame rate. Tolerates a truncated/corrupt footer.
"""
import struct, sys, av
from fractions import Fraction

def rvarint(b,p):
    s=v=0
    while True:
        x=b[p];p+=1;v|=(x&0x7f)<<s
        if not(x&0x80):break
        s+=7
    return v,p
def flds(b):
    p=0;o=[]
    while p<len(b):
        k,p=rvarint(b,p);fn=k>>3;wt=k&7
        if wt==0:v,p=rvarint(b,p);o.append((fn,v))
        elif wt==2:ln,p=rvarint(b,p);o.append((fn,b[p:p+ln]));p+=ln
        elif wt==5:o.append((fn,b[p:p+4]));p+=4
        elif wt==1:o.append((fn,b[p:p+8]));p+=8
        else:break
    return o
def ts_ns(b):
    s=n=0
    for fn,v in flds(b):
        if fn==1:s=v
        if fn==2:n=v
    return s*10**9+n

def parse(path):
    data=open(path,'rb').read()
    assert data[:8]==b"\x89MCAP0\r\n"
    schemas={};channels={};frames={}  # cid -> list[(pub_ns, ts_ns, data, keyframe)]
    def walk(buf):
        off=0
        while off+9<=len(buf):
            op=buf[off];length=struct.unpack_from('<Q',buf,off+1)[0];bs=off+9;be=bs+length
            if op not in range(1,16) or be>len(buf):
                return  # graceful stop at truncation/corruption
            body=buf[bs:be]
            if op==3:
                sid=struct.unpack_from('<H',body,0)[0];p=2
                nl=struct.unpack_from('<I',body,p)[0];p+=4;nm=body[p:p+nl].decode();p+=nl
                schemas[sid]=nm
            elif op==4:
                cid=struct.unpack_from('<H',body,0)[0];p=2
                sid=struct.unpack_from('<H',body,p)[0];p+=2
                tl=struct.unpack_from('<I',body,p)[0];p+=4;tp=body[p:p+tl].decode()
                channels[cid]=(tp,schemas.get(sid,''))
            elif op==6:
                p=24+4;cl=struct.unpack_from('<I',body,p)[0];p+=4+cl
                rl=struct.unpack_from('<Q',body,p)[0];p+=8;walk(body[p:p+rl])
            elif op==5:
                cid,seq=struct.unpack_from('<HI',body,0);lt,pt=struct.unpack_from('<QQ',body,6)
                nm=channels.get(cid,('',''))[1]
                if nm=='foxglove.CompressedVideo':
                    its=None;d=b'';fmt=''
                    for fn,v in flds(body[22:]):
                        if fn==1 and isinstance(v,bytes):its=ts_ns(v)
                        elif fn==3:d=v
                        elif fn==4 and isinstance(v,bytes):fmt=v.decode('utf8','replace')
                    frames.setdefault(cid,[]).append((pt,(its if its is not None else pt),d,fmt))
            off=be
    walk(data[8:])
    return channels,frames

def convert(path):
    channels,frames=parse(path)
    for cid,fr in frames.items():
        topic=channels[cid][0]
        fr.sort(key=lambda r:r[0])
        # write annex-B, then remux with real PTS
        tag=topic.strip('/').replace('/','_')
        es=tag+'.es.h265'
        open(es,'wb').write(b''.join(f[2] for f in fr))
        t0=fr[0][1]
        TB=90000
        inp=av.open(es)
        pkts=[p for p in inp.demux(inp.streams.video[0]) if p.size>0]
        out=av.open(tag+'.mp4','w')
        os_=out.add_stream_from_template(inp.streams.video[0])
        os_.time_base=Fraction(1,TB)
        n=min(len(fr),len(pkts))
        for i in range(n):
            pk=pkts[i];pts=round((fr[i][1]-t0)/1e9*TB)
            pk.pts=pk.dts=pts;pk.time_base=Fraction(1,TB);pk.stream=os_
            out.mux(pk)
        out.close();inp.close()
        span=(fr[-1][1]-fr[0][1])/1e9
        print(f"{topic}: {len(fr)} frames, true span {span:.4f}s -> {(len(fr)-1)/span:.3f} fps  =>  {tag}.mp4")

if __name__=='__main__':
    convert(sys.argv[1] if len(sys.argv)>1 else '/home/eric/Downloads/session_00064_71ac466b_ERROR.mcap')
