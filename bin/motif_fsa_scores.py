'''
More generic version of the logisitic function

Read in a fasta sequences, scan for every motif in a tamo file, produce numpy matrix as a result

'''

__author__="Sara JC Gosline, Chris W Ng"
__email__="sgosline@mit.edu"

from optparse import OptionParser

#import chipsequtil.Fasta as Fasta
import cPickle
import numpy as np
import math,sys
from multiprocessing import Pool
from csv import DictReader

import os,sys,re


def motif_bestscan_matrix(F,motif,outfile,genome):
    
    #Load motif and background adjust PSSM
    m=MotifTools.load(motif)


    seqs=F.values()
    n_seqs=len(seqs)
    n_motifs=len(m)
    SCORES=np.zeros((n_motifs,n_seqs),dtype='float')

    ##for now just create matrix of best scans
    for ind,mot in enumerate(m):
        for s_ind,seq in enumerate(seqs):
            SCORES[ind,s_ind]=mot.bestscan(seq.upper())


    ##save scores to file
    np.savetxt(outfile,SCORES,fmt='%.3f')
#############TRANSFAC SPECIFIC CODE
def load_ids(ids):
    '''
    Loads in TRANSFAC motif identifiers
    '''
    FH=open(ids)
    IDS=[]
    for line in FH:
        mid=line.rstrip('\n')
        IDS.append(mid)
    FH.close()
    return IDS

def motif_matrix(F,motif,outfile,genome,ids,pkl,threads,typ):
    '''
    Creates matrix of motif scan based on TRANSFAC match scores
    '''


    #Load motif and background adjust PSSM
    m=MotifTools.load(motif)

#    F=Fasta.load(fsa,key_func=lambda x:x)
    seqs=F.values()
    n_seqs=len(seqs)
    n_motifs=len(m)
    SCORES=np.zeros((n_motifs,n_seqs),dtype='float')
    
    #Load motif ids and profile pickle
    IDS=load_ids(ids)
    PRF=cPickle.load(open(pkl))

    z=zip(m,IDS)
    jobs=[]
    p=Pool(threads)
    for Z in z: jobs.append([Z,PRF,genome,seqs,typ])
    results=p.map(numbs,jobs)
    for i,r in enumerate(results): SCORES[i,:]=r

    np.savetxt(outfile,SCORES,fmt='%.3f')
    
def numbs(args):
    '''
    Calculates the score of all the matches in a particular binding region
    '''
    Z,PRF,genome,seqs,typ=args
    n_seqs=len(seqs)
    M,ID=Z
    thres,SUM,FP=PRF[ID]
    ll = M.logP

    if genome in ['hg18','hg19']:
        bg={'A': 0.26005923930888059,
            'C': 0.23994076069111939,
            'G': 0.23994076069111939,
            'T': 0.26005923930888059}
    elif genome in ['mm8','mm9','mm10']: 
        bg={'A': 0.29119881438474354,
        'C': 0.20880118561525646,
        'G': 0.20880118561525646,
        'T': 0.29119881438474354}
    else:
        bg={'A':0.25,'G':0.25,'C':0.25,'T':0.25}

    for pos in ll:
        for letter in pos.keys():
            pos[letter] = pos[letter] - math.log(bg[letter])/math.log(2.0)

    AM = MotifTools.Motif_from_ll(ll)
    mi,ma=AM.minscore,AM.maxscore
    AM.source = M.source
    t=thres*(ma-mi)+mi
    S=np.zeros((1,n_seqs),dtype='float')
    
    #Search every seq for given motif above threshold t and print motif centered results
    for j,seq in enumerate(seqs):
        try:
            seq_fwd = seq.upper()
            matches,endpoints,scores=AM.scan(seq_fwd,threshold=t)
            s=[(x-mi)/(ma-mi) for x in scores]
            aff=affinity(s,SUM,FP,typ==typ)
            #num_bs=len(scores)
            S[0,j]=aff
        except: 
            S[0,j]=0
            #print 'score calc exception',
    return S

def affinity(scores,SUM,FP,typ=1):
    '''
    takes the afinity based on the FP score (which is just .5?)
    '''
    if typ==0:
        try: w=math.log(9)/(FP-SUM)
        except: w=math.log(9)/0.1
        b=math.exp(w*SUM)
    else: #default to this
        try: w=math.log(6.)/(FP-SUM)
        except: w=math.log(6.)/0.1
        b=4*math.exp(w*SUM)
        #try: w=2*math.log(7/3.)/(FP-SUM)
        #except: w=2*math.log(7/3.)/0.1
        #b=7/3*math.exp(w*SUM)
    a=0
    for x in scores: a+=math.exp(w*x)
    A=a/(b+a)
    return A

def reduce_fasta(fsa_dict,gene_file):
    '''
    Takes FASTA file and reduces events to those found in gene_file
    '''
    ##first open gene file and get mids that map to a gene
    mapped_mids=set()
    closest_gene=DictReader(open(gene_file,'rU'),delimiter='\t')
    count=0
    for g in closest_gene:
        mapped_mids.add(g['chrom']+':'+str(int(g['chromStart'])+(int(g['chromEnd'])-int(g['chromStart']))/2))
        count=count+1
    ##then reduce fasta dict to only get those genes that map
    new_seq={}    
  #  print ','.join([k for k in mapped_mids][0:10])

    for k in fsa_dict.keys():
        vals=k.split(';')
        if len(vals)==1:
            vals=k.split(' ')
        #print vals
        if ':' in vals[0]: #just in case bedtools were used 
            chr,range=vals[0].split(':')
            low,high=range.split('-')
            mid=str(int(low)+((int(high)-int(low))/2))
            seq_mid=chr+':'+mid
        elif 'random' not in vals[0]: #galaxy tools used, but no random found
            allvals=vals[0].split('_')
            #            genome,chr,low,high,strand=vals[0].split('_')
            if(len(allvals)<4):
                print 'Cannot find sequence data for '+vals[0]
            else:
                genome=allvals[0]
                chr=allvals[1]
                low=allvals[2]
                high=allvals[3]
            mid=str(int(low)+((int(high)-int(low))/2))
            seq_mid=chr+':'+mid
        #print seq_mid
        if seq_mid in mapped_mids:
            new_seq[k]=fsa_dict[k]
    
    print 'Found '+str(len(new_seq))+' events from FASTA file that map to '+str(count)+' event-gene matches out of '+str(len(fsa_dict))+' events'

    ##now write new fasta file
    Fasta.write(new_seq,re.sub('.xls','.fsa',gene_file))
    return new_seq
    

##get program directory
progdir=os.path.dirname(sys.argv[0])

def main():
    usage = "usage: %prog [opts] fasta_file"
    srcdir=os.path.join(progdir,'../src')

    parser=OptionParser(usage)
    
    parser.add_option("--motif", dest="motif",default=os.path.join(progdir,"../data/matrix_files/vertebrates_clustered_motifs.tamo"),help='The .tamo formatted motif file to use for motif matching and scoring')
    parser.add_option('--scores',dest='pkl',default=os.path.join(progdir,'../data/matrix_files/motif_thresholds.pkl'),help='PKL file of matrix score thresholds')
    parser.add_option('--ids',dest='ids',default=os.path.join(progdir,'../data/matrix_files/vertebrates_clustered_motifs_mIDs.txt'),help='List of Exemplar motifs in motif cluster')
    
    parser.add_option('--genefile',dest='gene_file',default='',help='File indicating which regions are mapped to genes, enabling the reduction of the FASTA file for gene-relevant regions')
    parser.add_option("--genome", dest="genome", default='mm9',help='The genome build that you are using, used to estimate binding site priors')
    parser.add_option('--utilpath',dest='addpath',default=srcdir,help='Destination of chipsequtil library, Default=%default')
    parser.add_option("--outfile", dest="outfile")

#    parser.add_option('--logistic',dest='logistic',action='store_true',default=False,help='Set to true to scale multiple matches into a logistic curve')
    parser.add_option('--threads',dest='threads',type='string',default='4',help='Set number of threads if using logistic scoring')
    
    (opts, args) = parser.parse_args()
    if len(args) != 1:
        parser.error("incorrect number of arguments")
        
    fsa=args[0]
    motiffile=opts.motif
    ##append path to chipsequtil/TAMO
    sys.path.insert(0,opts.addpath)
    global MotifTools
    from chipsequtil import motiftools as MotifTools #import chipsequtil.motiftools as MotifTools
    global Fasta
    from chipsequtil import Fasta
#    sys.path.insert(0,opts.addpath+'chipsequtil')
    
    fsa_dict=Fasta.load(fsa,key_func=lambda x:x)
    if opts.gene_file!='':
        print 'Reducing FASTA file to only contain sequences from '+opts.gene_file
        fsa_dict=reduce_fasta(fsa_dict,opts.gene_file)


    motif_matrix(fsa_dict,motiffile,opts.outfile,opts.genome,opts.ids,opts.pkl,int(opts.threads),typ=1)

if __name__=='__main__':
    main()
