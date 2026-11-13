/** Preserve the initial exports and add the exact merged alignment in a versioned copy. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const workspace=path.resolve(process.argv[2]);
const {msasFromArchive}=await import(pathToFileURL(path.join(workspace,'work/vendor/localfold/web/fold-archive.js')));
for(const name of ['localfold-il7-control-v1','localfold-seed43-v1','localfold-seed44-v1']) {
  const folder=path.join(workspace,'outputs/execution-evidence',name);
  const out=path.join(folder,'archive-with-msa-v2');
  await fs.mkdir(out);
  const files=new Map();
  for(const filename of await fs.readdir(path.join(folder,'archive'))) {
    const data=await fs.readFile(path.join(folder,'archive',filename),'utf8');
    files.set(filename,data);await fs.writeFile(path.join(out,filename),data);
  }
  const msa=await fs.readFile(path.join(folder,'complex.a3m'),'utf8');
  const filename='msas/localfold_qualification_merged_msa.a3m';
  files.set(filename,msa);await fs.mkdir(path.join(out,'msas'));
  await fs.writeFile(path.join(out,filename),msa);
  if(msasFromArchive(files).merged!==msa)throw new Error('Archive MSA round trip failed');
  await fs.writeFile(path.join(folder,'archive-repair-audit.json'),JSON.stringify({
    status:'derived_export_checked',original_archive_preserved:true,inference_rerun:false,
    diagnosis:'Harness initially passed msas.complex; upstream archive API expects msas.merged.',
    added_alignment_sha256:createHash('sha256').update(msa).digest('hex'),round_trip_checked:true,
    submission_eligible:false},null,2)+'\n');
}
console.log('Three versioned exports retain and round-trip their exact inference alignment');
