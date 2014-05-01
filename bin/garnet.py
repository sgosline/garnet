#!/usr/bin/python
'''

GARNET primary script executes 5 sub scripts according to provided configuration file. We provide vertebrate motif data and gene/xref data for hg19 and mm9. 
--------------------------------------------------------------------
Config file:
--------------------------------------------------------------------
Configuration file should have 11 different varaibles provided.
[chromatinData]
bedfile=[bed file of accessible chromatin regions]
fastafile=[fasta file of same regions, collected via galaxyweb]

genefile=[path to garnet]/examples/ucsc_hg19_knownGenes.txt
xreffile=[path to garnet]/examples/ucsc_hg19_kgXref.txt

windowsize=[distance around transcription starte site]

[motifData]
tamo_file=../data/matrix_files/vertebrates_clustered_motifs.tamo
genome=hg19
numthreads=4
doNetwork=False

[expressionData]
expressionFile=[name of expression file]
=======================================================================

'''

__author__='Sara JC Gosline'
__email__='sgosline@mit.edu'

##update this to include direct location of chipsequtil pacakge
import sys,os,re
from optparse import OptionParser
from ConfigParser import ConfigParser

progdir=os.path.dirname(sys.argv[0])


def mapGenesToRegions(genefile,xreffile,bedfile,window='2000'):
    '''
    First step of GARNET maps exposed regions in bedfile to closest gene wtihin rpovided window
    calls map_peaks_to_known_genes.py
    '''
    outfile=os.path.splitext(os.path.basename(bedfile))[0]+'eventsWithin'+window+'bp_of_'+os.path.splitext(os.path.basename(genefile))[0]+'.xls'

    ##Step 1: map chromatin regions to nearby genes/transcription start sites
    cmd='python '+os.path.join(progdir,'map_peaks_to_known_genes.py')+' --peaks-format=BED --utilpath='+os.path.join(progdir,'../src/')+' --upstream-window='+window+' --downstream-window='+window+' --tss --map-output='+outfile+' '+genefile+' '+xreffile+' '+bedfile
    if not os.path.exists(outfile):
        print cmd
        print 'Output-----------------------------mapGenesToRegion------------------------------------------'
        print 'Mapping genes from '+genefile+' to regions within '+window+' bp of events from '+bedfile+' and putting results in '+outfile
        os.system(cmd)
    else:
        print 'File '+outfile+' already exists. If you would like to replace it, delete and re-run'

    return outfile


def motifScanning(tamo_file,fastafile,numthreads,genome,closest_gene_file=''):
    '''
    Second step of GARNET scans chromatin regions provided in galaxy-produced FASTA for motif matrix 
    affinity scores
    '''
    if closest_gene_file=='':
        motif_binding_out=re.sub('.fasta','_'+re.sub('.tamo','',os.path.basename(tamo_file))+'_motifs.txt',os.path.basename(fastafile))
    else:
        motif_binding_out=re.sub('.xls','_'+re.sub('.tamo','',os.path.basename(tamo_file))+'_motifs.txt',os.path.basename(closest_gene_file))


    if os.path.exists(motif_binding_out):
        print 'Intermediate file '+motif_binding_out+' already exists, if you would like to replace, delete and re-run'
        return motif_binding_out


    scan_cmd='python '+os.path.join(progdir,'motif_fsa_scores.py')+' --motif='+tamo_file+' --genome='+genome+' --outfile='+motif_binding_out+' --genefile='+closest_gene_file+' --scale=10 --threads='+numthreads+' '+fastafile
    print scan_cmd
    print 'Output-----------------------------motifScanning------------------------------------------'
    print 'Scanning regions from '+fastafile+' using matrices from '+tamo_file+' and putting results in '+motif_binding_out
    os.system(scan_cmd)
    return motif_binding_out

def createBindingMatrix(motif_binding_out,outfile,fastafile,tamo_file,use_uniprot=False):
    '''
    Third step of GARNET merges motif scores with closest gene information to create motif/gene 
    scoring matrix with appropriate identifiers
    '''
    if use_uniprot:
        tfs=re.sub('.tamo','_up_tfids.txt',tamo_file)
        matfile=re.sub('.txt','.tgm',os.path.basename(motif_binding_out))
    else:
        matfile=re.sub('.txt','.tgm',os.path.basename(motif_binding_out))
        tfs=re.sub('.tamo','_tfids.txt',tamo_file)

    if use_uniprot:
        ##using uniprot identifiers here
        map_cmd='python '+os.path.join(progdir,'get_window_binding_matrix.py')+' '+motif_binding_out+' '+outfile+' '+' '+fastafile+" --distance-to-gene='' --motif-id-list="+tfs+' --outfile='+matfile
    else:
        ##using regular gene names here
        map_cmd='python '+os.path.join(progdir,'get_window_binding_matrix.py')+' '+motif_binding_out+' '+outfile+' '+' '+fastafile+" --distance-to-gene='' --motif-id-list="+tfs+' --outfile='+matfile

    pklfile=re.sub('.tgm','.pkl',matfile)
    if os.path.exists(pklfile):
        print 'Intermediate file '+pklfile+' already exists, if you would like to replace delete and re-run'
        return pklfile

    print map_cmd
    print 'Output-----------------------------createBindingMatrix------------------------------------------'
    os.system(map_cmd)
    
    return pklfile


def getTfsFromRegression(pickle_file,expressionfile):
    '''
    Fourth step of GARNET is to perform regression with pickled matrix file and expression data
    '''
    print 'Running regression using '+expressionfile+' expression data and '+pickle_file+' binding data'
#    tgm_base=re.sub('.tgm','',matrix_file)
#    tfids=tgm_base+'_tfids.txt'
#    gids=tgm_base+'_geneids.txt'

    outdir=os.path.basename(expressionfile).split('.')[-2]+'_'+re.sub('.pkl','',os.path.basename(pickle_file))+'.xls'
    print outdir
    if not os.path.exists(outdir):
        cmd='python '+os.path.join(progdir,'motif_regression.py')+' --outdir='+outdir+' '+pickle_file+' '+expressionfile
        print cmd
        print 'Output-----------------------------getTfsFromRegression------------------------------------------'
        os.system(cmd)
    return outdir
    
def main():
    
    srcdir=os.path.join(progdir,'../src')
    
    usage='Usage: %prog [configfilename]'
    parser=OptionParser(usage=usage)
    parser.add_option('--useUniprot',dest='useUniprot',action='store_true',help='Set this flag to use Uniprot identifies',default=False)
    parser.add_option('--utilpath',dest='addpath',help='Destination of chipsequtil library, Default=%default',default=srcdir)


    opts,args=parser.parse_args()
    
    sys.path.insert(0,opts.addpath)
    sys.path.insert(0,opts.addpath+'chipsequtil')
    
    if len(args)!=1:
        print 'Need a configuration file to provide experiment-level details'
        sys.exit()

    config=ConfigParser()
    config.read(args[0])

    ##now check for elements of config file. if they are missing, move onto next step
    ##first step 1 check
    genefile=config.get('chromatinData','genefile')
    bedfile=config.get('chromatinData','bedfile')
    xref=config.get('chromatinData','xreffile')

    window=config.get('chromatinData','windowsize')
    if window is None:
        window='2000'    

    if genefile is not None and bedfile is not None and xref is not None:
        outfile=mapGenesToRegions(genefile,xref,bedfile,window)
    else:
        print 'Missing genefile,bedfile or xref file, cannot map genes to regions.'
        system.exit()

    tamofile=config.get('motifData','tamo_file')
    genome=config.get('motifData','genome')
    
    numthreads=config.get('motifData','numthreads')
    if numthreads is None:
        numthreads='1'

    fastafile=config.get('chromatinData','fastafile')

    ##step 2
    if tamofile is not None and tamofile!='' and genome is not None and fastafile is not None and fastafile!='':
        if os.path.exists(tamofile) and os.path.exists(fastafile):
            binding_out=motifScanning(tamofile,fastafile,numthreads,genome,outfile)
        else:
            binding_out=''
            print 'Missing FASTA file or TAMO file - check your config file and try again.'



    ##step 3
    newfasta=re.sub('.xls','.fsa',outfile)
    if outfile is not None and outfile!='' and binding_out is not None and binding_out!='':
        binding_matrix=createBindingMatrix(binding_out,outfile,newfasta,tamo_file=tamofile,use_uniprot=opts.useUniprot)
    else:
        binding_matrix=''

#        pklfile=config.get('motifData','pkl')
    do_network=config.get('motifData','doNetwork')
    ##Step 4.5
#    if pklfile is not None and pklfile!='' and os.path.exists(binding_matrix):
#            cmd='python '+os.path.join(progdir,'zipTgms.py')+' '+binding_matrix+' '+re.sub('.tgm','_tfids.txt',binding_matrix)+' '+re.sub('.tgm','_geneids.txt',binding_matrix)+' --pkl='+pklfile+' --tf-delimiter=. --genome='+genome
    if do_network is not None and do_network!='' and do_network!='False':
        cmd='python '+os.path.join(progdir,'zipTgms.py')+' --pkl='+binding_matrix+' --genome '+genome+' --as-network'
        print cmd
        os.system(cmd)

    expr=config.get('expressionData','expressionFile')
    ##step 4: regression
    if expr is not None and expr!='':
        #print binding_matrix,expr
        if binding_matrix!='' and os.path.exists(binding_matrix) and os.path.exists(expr):
            tfs=getTfsFromRegression(binding_matrix,expr)
        else:
            print 'Cannot perform regression because binding matrix or expression datasets are missing'
    
    
if __name__=='__main__':
    main()
