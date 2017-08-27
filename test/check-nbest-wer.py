#!/usr/bin/env python
import re, sys, os
from collections import defaultdict

def RunRegressionPrep () :
    print "Standard alignment"
    command = """phonetisaurus-align --input=g014b2b/g014b2b.train \
    --ofile=g014b2b/g014b2b.corpus \
    --seq1_del=false \
    --grow=false
    """
    os.system (command)

    print "Alignment with support for growing"
    command = """phonetisaurus-align --input=g014b2b/g014b2b.train \
    --ofile=g014b2b/g014b2b.grow.corpus \
    --seq1_del=false \
    --grow=true
    """
    os.system (command)

    print "\nTraining standard ARPA"
    command = """estimate-ngram -o 8 -t g014b2b/g014b2b.corpus \
    -wl g014b2b/g014b2b.o8.arpa
    """
    os.system (command)

    print "Training grow-supported ARPA"
    command = """estimate-ngram -o 8 -t g014b2b/g014b2b.grow.corpus \
    -wl g014b2b/g014b2b.grow.o8.arpa
    """
    os.system (command)

    print "\nConverting stanard model to Fst"
    command = """phonetisaurus-arpa2wfst --lm=g014b2b/g014b2b.o8.arpa \
    --ofile=g014b2b/g014b2b.o8.fst
    """
    os.system (command)

    print "Converting grow-reported stanard model to Fst"
    command = """phonetisaurus-arpa2wfst --lm=g014b2b/g014b2b.grow.o8.arpa \
    --ofile=g014b2b/g014b2b.grow.o8.fst
    """
    os.system (command)

    print "\nTesting 5-best standard"
    command = """phonetisaurus-g2pfst --model=g014b2b/g014b2b.o8.fst \
    --wordlist=g014b2b/g014b2b.words \
    --nbest=5 | perl -e'while(<>){s/\|/ /g; print $_;}' \
    > g014b2b/g014b2b-n5.hyp
    """
    os.system (command)

    print "Testing 5-best grow-supported standard"
    command = """phonetisaurus-g2pfst --model=g014b2b/g014b2b.grow.o8.fst \
    --wordlist=g014b2b/g014b2b.words \
    --nbest=5 | perl -e'while(<>){s/\|/ /g; print $_;}' \
    > g014b2b/g014b2b-grow-n5.hyp
    """
    os.system (command)

    return

def LoadRefs (refs_file) :
    refs = {}

    with open (refs_file, "r") as ifp :
        for line in ifp :
            parts = re.split (ur"\t", line.decode ("utf8").strip ())
            word = parts.pop (0)
            refs [word] = parts

    return refs

def LoadNbestHyps (hyps_file) :
    hyps = defaultdict (list)

    with open (hyps_file, "r") as ifp :
        for line in ifp :
            parts = re.split (ur"\t", line.decode ("utf8").strip ())
            if parts [-1] == "" :
                continue

            hyps [parts [0]].append (parts [-1])

    return hyps

def ComputeEval (hyps) :
    refs = LoadRefs ("g014b2b/g014b2b.ref")
    hyps = LoadNbestHyps (hyps)

    total = 0.
    corr = 0.
    for ref_word, ref_prons in refs.iteritems () :
        hyp_prons = hyps [ref_word]
        ref_set = set (ref_prons)
        hyp_set = set (hyp_prons)
        intersection = ref_set.intersection (hyp_set)

        total += 1.0
        if len (intersection) > 0 :
            corr += 1.0

    print "Corr: {0}, Err: {1}, WACC: {2:0.2f}%, WER: {3:0.2f}%".format (
        corr,
        total - corr,
        corr / total * 100,
        (1.0 - (corr / total)) * 100
    )


if __name__ == "__main__" :
    import argparse

    example = "{0} --prefix g014b2b".format (sys.argv [0])
    parser = argparse.ArgumentParser (description=example)
    parser.add_argument ("--prefix", "-p", help="Prefix.",
                         default="g014b2b")
    args = parser.parse_args ()

    RunRegressionPrep ()
    ComputeEval ("{0}/{0}-n5.hyp".format (args.prefix))
    ComputeEval ("{0}/{0}-grow-n5.hyp".format (args.prefix))
