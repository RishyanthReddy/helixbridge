/** Bounded LocalFold AF2-Multimer qualification; every output is diagnostic. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const options=Object.fromEntries(process.argv.slice(2).map(x=>{const i=x.indexOf('=');return [x.slice(2,i),x.slice(i+1)];}));
const workspace=path.resolve(options.workspace);
const source=path.join(workspace,'work/vendor/localfold');
const output=path.resolve(options.output);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const load=relative=>import(pathToFileURL(path.join(source,relative)));
const revision=execFileSync('git',['-C',source,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
if(revision!=='0724b7fcebd9a83d263d9d9c485f818dce0242a1'
   ||execFileSync('git',['-C',source,'status','--porcelain','--untracked-files=no'],{encoding:'utf8'}).trim())
  throw new Error('Unreviewed LocalFold source');
await fs.mkdir(path.dirname(output),{recursive:true});
await fs.mkdir(output);
const started=performance.now();
let device;
const save=async(name,value)=>fs.writeFile(path.join(output,name),JSON.stringify(value,null,2)+'\n');
try {
  const {MODEL_BUNDLES,loadManifest}=await load('shared/bundles/manifests/index.js');
  const bundle=MODEL_BUNDLES.multimer;
  const cache=options.bundle?path.resolve(options.bundle):path.join(workspace,'work/localfold-weights/int5');
  await fs.mkdir(cache,{recursive:true});
  const manifest=options.bundle?JSON.parse(await fs.readFile(path.join(cache,'manifest.json'),'utf8')):await loadManifest('multimer');
  const files=[...new Set(Object.values(manifest.tensors).map(x=>x.file))];
  const fileHashes={};
  await Promise.all(files.map(async filename=>{
    const filenamePath=path.join(cache,filename);
    let bytes;
    try {bytes=await fs.readFile(filenamePath);} catch(error) {
      if(options.bundle||error.code!=='ENOENT')throw error;
      const response=await fetch(new URL(filename,bundle.remote));
      if(!response.ok)throw new Error('Weight download failed: '+response.status);
      bytes=Buffer.from(await response.arrayBuffer());
      if(sha(bytes)!==manifest.shardDigests[filename])throw new Error('Downloaded shard hash mismatch');
      await fs.writeFile(filenamePath,bytes,{flag:'wx'});
    }
    fileHashes[filename]=sha(bytes);
    if(manifest.shardDigests?.[filename]&&fileHashes[filename]!==manifest.shardDigests[filename])throw new Error('Cached shard hash mismatch');
  }));
  if(!options.bundle)await fs.writeFile(path.join(cache,'manifest.json'),JSON.stringify(manifest));
  const originalFetch=globalThis.fetch;
  globalThis.fetch=async(url,init)=>{
    const u=new URL(url);
    if(u.origin==='https://localfold-qualification.invalid') {
      const filename=path.basename(u.pathname);
      if(!files.includes(filename))throw new Error('Unreviewed tensor request');
      return new Response(await fs.readFile(path.join(cache,filename)));
    }
    return originalFetch(url,init);
  };
  const require=createRequire(path.join(workspace,'work/localfold-runtime/package.json'));
  const binding=await import(require.resolve('webgpu'));
  Object.assign(globalThis,binding.globals);
  const gpu=binding.create([]);
  const adapter=await gpu.requestAdapter({powerPreference:'high-performance'});
  if(!adapter)throw new Error('No hardware WebGPU adapter');
  const {requestAlphaFoldDevice}=await load('webgpu/runtime/device.js');
  device=await requestAlphaFoldDevice(adapter,{memoryBudgetBytes:4*1024**3});
  if(options.precision==='f32') {
    const {setDeviceTuning}=await load('webgpu/runtime/device-profile.js');
    setDeviceTuning(device,{halfPrecision:false});
  }
  if(manifest.bundle.encoding==='float32-le') {
    // Float32 weights have no quantized codes for the device decoder. Only
    // weight packing runs on the host; all neural-network operations stay WebGPU.
    const {setDeviceTuning}=await load('webgpu/runtime/device-profile.js');
    setDeviceTuning(device,{allowHostWeightPacking:true});
  }
  const {HttpTensorStore}=await load('shared/bundles/http-tensor-store.js');
  const {AlphaFoldFixture}=await load('shared/bundles/alphafold-fixture.js');
  const store=await HttpTensorStore.fromManifest('https://localfold-qualification.invalid/manifest.json',manifest);
  store.prefetch();
  const fixture=AlphaFoldFixture.fromStore(store);
  const [embedding,templateEmbedding,extraStack,mainStack,structure,confidence,geometry,featureTables,paeBreaks]=await Promise.all([
    fixture.embeddingWeights(),fixture.templateEmbeddingWeights(),fixture.extraStackWeights(),fixture.mainStackWeights(),
    fixture.structureWeights(),fixture.confidenceWeights(),fixture.geometryTables(),fixture.queryOnlyFeatureTables(),fixture.tensor('confidencePaeBreaks')]);
  const weights={embedding,templateEmbedding,extraStack,mainStack,structure,lddt:confidence.lddt,pae:confidence.pae,geometry};
  const {AlphaFoldUnifiedGpu}=await load('webgpu/af2/multimer/model.js');
  let sequence,chainSequences,chainLengths,prediction,inputHash;
  const settings={recycles:3,randomSeed:0,maxMsaSequences:128,maxExtraSequences:128,
    outerProductMeanFirst:true,positionScale:20,chainAware:true,tolerance:0,hostFeaturisation:true,
    compute_precision:options.precision??'auto'};
  const runner=new AlphaFoldUnifiedGpu(device);
  if(options.oracle) {
    const raw=await fs.readFile(options.oracle); inputHash=sha(raw);
    const oracle=JSON.parse(raw); const n=oracle.length;
    sequence=oracle.sequence; chainLengths=oracle.chain_lengths;
    chainSequences=chainLengths.map((count,i)=>sequence.slice(chainLengths.slice(0,i).reduce((a,b)=>a+b,0),chainLengths.slice(0,i+1).reduce((a,b)=>a+b,0)));
    const f=oracle.features;
    const f32=name=>Float32Array.from(f[name]);
    const aatype=f32('aatype'),targetFeatures=new Float32Array(n*22);
    const atom37ToAtom14=new Float32Array(n*37),atom37Mask=new Float32Array(n*37);
    for(let i=0;i<n;i++) {
      targetFeatures[i*22+1+aatype[i]]=1;
      atom37ToAtom14.set(featureTables.atom37ToAtom14.subarray(aatype[i]*37,(aatype[i]+1)*37),i*37);
      atom37Mask.set(featureTables.atom37Mask.subarray(aatype[i]*37,(aatype[i]+1)*37),i*37);
    }
    const feats={aatype,targetFeatures,msaFeatures:f32('msa_feat'),msaMask:f32('msa_mask'),
      extraMsa:f32('extra_msa'),extraHasDeletion:f32('extra_has_deletion'),extraDeletionValue:f32('extra_deletion_value'),
      extraMsaMask:f32('extra_msa_mask'),residueIndex:f32('residue_index'),seqMask:f32('seq_mask'),
      asymId:f32('asym_id'),entityId:f32('entity_id'),symId:f32('sym_id'),atom37ToAtom14,atom37Mask,
      msaSequences:oracle.msa_sequences,extraSequences:oracle.extra_sequences,targetChannels:22,msaFeatureChannels:49};
    settings.recycles=0;
    prediction=await runner.predict([feats],weights,paeBreaks,undefined,undefined,{...settings,chainLengths,chainSequences,pairHost:true});
  } else {
    const raw=await fs.readFile(options.input); inputHash=sha(raw);const request=JSON.parse(raw);
    if(request.partner.msa!==null)throw new Error('Qualification requires target-only MSA');
    chainSequences=[request.target.sequence,request.partner.sequence];
    chainLengths=chainSequences.map(x=>x.length); sequence=chainSequences.join('');
    const msaPath=path.join(workspace,'pipeline',request.target.msa);
    const msa=await fs.readFile(msaPath,'utf8');const records=[];
    for(const line of msa.split(/\r?\n/)) {
      if(line.startsWith('>'))records.push({header:line,sequence:''});
      else if(records.length)records.at(-1).sequence+=line.trim();
    }
    if(records[0].sequence.replace(/[a-z.]/g,'')!==chainSequences[0])throw new Error('Target MSA identity mismatch');
    const a3m=records.slice(0,1024).map((row,i)=>`${row.header}\n${row.sequence}${i===0?chainSequences[1]:'-'.repeat(chainLengths[1])}`).join('\n')+'\n';
    await fs.writeFile(path.join(output,'complex.a3m'),a3m);
    await save('input.json',request);
    prediction=await runner.predictA3m(a3m,weights,featureTables,{...settings,chainLengths,chainSequences},paeBreaks,
      (_,recycle)=>console.log(JSON.stringify({event:'recycle_complete',recycle})),
      progress=>{if(progress.waiting)console.log(JSON.stringify({event:'progress',completed:progress.completed,total:progress.total}));});
  }
  const final=prediction.final,n=sequence.length;
  for(const [name,array] of Object.entries({coordinates:final.structure.atom37,pae:final.confidence.predictedAlignedError}))
    if(!Array.from(array).every(Number.isFinite))throw new Error('Nonfinite '+name);
  if(final.confidence.predictedAlignedError.length!==n*n)throw new Error('PAE dimension mismatch');
  const {predictionToPdb}=await load('web/prediction-results.js');
  const pdb=predictionToPdb(sequence,final.structure,final.confidence.plddt,chainLengths);
  await fs.writeFile(path.join(output,'model.pdb'),pdb);
  await save('raw.json',{sequence,chain_lengths:chainLengths,pae:Array.from(final.confidence.predictedAlignedError),
    plddt:Array.from(final.confidence.plddt),pair:options.oracle?Array.from(final.pair):undefined,
    ca:options.oracle?Array.from({length:n*3},(_,i)=>final.structure.atom37[(Math.floor(i/3)*37+1)*3+i%3]):undefined});
  const {buildFoldArchive}=await load('web/fold-archive.js');
  const archive=buildFoldArchive({stem:'localfold_qualification',model:'AlphaFold2-Multimer model1 '+manifest.bundle.encoding,
    settings:{...settings,seed:settings.randomSeed},entities:chainSequences.map(value=>({type:'protein',value,copies:1})),
    prediction:{confidence:final.confidence,pdb,chainLengths},msas:options.oracle?{}:{merged:await fs.readFile(path.join(output,'complex.a3m'),'utf8')},
    msaOrigin:'imported target-only MSA; no binder MSA; no templates supplied'});
  await fs.mkdir(path.join(output,'archive'));
  for(const [name,value] of archive) {
    const dest=path.join(output,'archive',name);await fs.mkdir(path.dirname(dest),{recursive:true});await fs.writeFile(dest,value);
  }
  const {memorySnapshot}=await load('webgpu/runtime/device-memory.js');
  await save('audit.json',{status:'diagnostic_qualification_only',submission_eligible:false,source_revision:revision,
    adapter_sha256:sha(await fs.readFile(new URL(import.meta.url))),input_sha256:inputHash,
    model:manifest.model,encoding:manifest.bundle.encoding,manifest_sha256:sha(JSON.stringify(manifest)),shard_sha256:fileHashes,
    settings,chain_lengths:chainLengths,sequence,iptm:final.confidence.iptm,ptm:final.confidence.ptm,
    mean_plddt:final.confidence.meanPlddt,elapsed_seconds:(performance.now()-started)/1000,memory:memorySnapshot(device),
    platform:'Mac Apple M3, Node Dawn WebGPU; not an L40S throughput measurement',
    native_reference_qualified:false,artifacts:{'model.pdb':sha(pdb),'raw.json':sha(await fs.readFile(path.join(output,'raw.json')))}});
  console.log('LocalFold qualification output complete');
  device.destroy();process.exit(0);
} catch(error) {
  await save('failure.json',{status:'failed',error:String(error.stack),elapsed_seconds:(performance.now()-started)/1000});
  device?.destroy();console.error(error);process.exit(1);
}
