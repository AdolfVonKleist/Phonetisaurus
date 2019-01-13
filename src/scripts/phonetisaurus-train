#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
from __future__ import print_function
import os, logging, subprocess, time, re
from datetime import datetime


class G2PModelTrainer () :
    """G2P Model training wrapper class.

    Phonetisaurus G2P modeling training wrapper class.
    This wraps the alignment, joint n-gram training, and ARPA to
    WFST conversion steps into one command.
    """

    def __init__ (self, lexicon_file, **kwargs) :
        self.lexicon_file = lexicon_file
        self.model_prefix = kwargs.get ("model_prefix", "model")
        self.dir_prefix = kwargs.get ("dir_prefix", "train")
        self.ngram_order = kwargs.get ("ngram_order", 8)
        self.seq1_max = kwargs.get ("seq1_max", 2)
        self.seq2_max = kwargs.get ("seq2_max", 2)
        self.seq1_del = kwargs.get ("seq1_del", False)
        self.seq2_del = kwargs.get ("seq2_del", False)
        self.grow = kwargs.get ("grow", False)
        self.verbose = kwargs.get ("verbose", False)
        self.logger = self.setupLogger ()
        self.makeJointNgramCommand = self._setLMCommand (
            kwargs.get ("lm", "mitlm")
        )

    def setupLogger (self) :
        """Setup the logger and logging level.

        Setup the logger and logging level.  We only support
        verbose and non-verbose mode.

        Args:
            verbose (bool): Verbose mode, or not.

        Returns:
            Logger: A configured logger instance.
        """

        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig (
            level=level,
            format="\033[94m%(levelname)s:%(name)s:"\
            "%(asctime)s\033[0m:  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        return logging.getLogger ("phonetisaurus-train")

    def validateLexicon (self) :
        """Validate the input training lexicon.

        Validate the input training lexicon.  At present
        this simply checks if the default reserved characters,
        ['}', '|', '_'], are used present in the lexicon.
        """

        validator_pattern = u"[\\}\\|_]" # python2: unicode, python3: str
        validator = re.compile (validator_pattern)

        with open (self.lexicon_file, "r") as ifp :
            for line in ifp :
                # in python 2, line will be byte
                # in python 3, line will be str
                if(type(line) is not type(validator_pattern)):
                    # in python 2, convert byte to unicode
                    line=line.decode("utf8")
                if validator.search (line) :
                    error = "Bad line contains reservered character:\n\t{0}"
                    error = error.format (line)
                    raise ValueError(error)

        return

    def checkPhonetisaurusConfig (self) :
        """Run some basic checks before training.

        Run some basic checks regarding the $PATH, environment,
        and provided data before starting training.

        Raises:
            EnvironmentError: raised if binaries are not found.
        """

        self.logger.info ("Checking command configuration...")
        for program in ["phonetisaurus-g2pfst",
                        "phonetisaurus-align",
                        "phonetisaurus-arpa2wfst"] :
            if not self.which (program) :
                raise EnvironmentError(
                    ", ".join([
                        "Phonetisaurus command, '{0}'",
                        "not found in path."
                    ]).format (program)
                )

        if not os.path.isdir (self.dir_prefix) :
            self.logger.debug ("Directory does not exist.  Trying to create.")
            os.makedirs (self.dir_prefix)

        self.logger.info (
            "Checking lexicon for reserved characters: '}', '|', '_'..."
        )
        self.validateLexicon ()

        path_prefix = os.path.join (self.dir_prefix, self.model_prefix)

        self.corpus_path = u"{0}.corpus".format (path_prefix)
        self.arpa_path = u"{0}.o{1}.arpa".format (path_prefix, self.ngram_order)
        self.model_path = u"{0}.fst".format (path_prefix)

        #for key,val in sorted (vars (self).iteritems ()) : # python2
        #for key,val in sorted (vars (self).items ()) : # python3
        #for key,val in sorted (six.iteritems(vars(self))) : # python2 or 3
        if 'iteritems' in dir(vars(self)):
            items = vars(self).iteritems()
        else:
            items = vars(self).items()
        for key,val in sorted(items):
            self.logger.debug (u"{0}:  {1}".format (key, val))

        return

    def which (self, program) :
        """Basic 'which' implementation for python.

        Basic 'which' implementation for python from stackoverflow:
          * https://stackoverflow.com/a/377028/6739158
        """

        def is_exe (fpath) :
            return os.path.isfile (fpath) and os.access (fpath, os.X_OK)

        fpath, fname = os.path.split (program)
        if fpath:
            if is_exe (program):
                return program
        else:
            for path in os.environ["PATH"].split (os.pathsep) :
                path = path.strip ('"')
                exe_file = os.path.join (path, program)
                if is_exe (exe_file):
                    return exe_file

        return None

    def _setLMCommand (self, lm) :
        """Configure the LM training command.

        Configure the LM training command according to the LM toolkit
        selected by the user.  Currently only mitlm is supported.

        Args:
            lm (str): The selected command type: 'mitlm'.

        Returns:
            function: The command building function for the selected toolkit.
        """
        if lm == "mitlm" :
            if self.which ("estimate-ngram") == None :
                raise EnvironmentError(
                    " ".join([
                        "mitlm binary 'estimate-ngram' not ",
                        "found in path."
                    ])
                )
            return self._mitlm
        else :
            raise NotImplementedError("Only mitlm is currently supported.")


    def _mitlm (self) :
        """mitlm estimate-ngram joint ngram training command.

        Build the mitlm joint ngram training command using the
        estimate-ngram utility and provided arguments.

        Returns:
            list: The command in subprocess list format.
        """

        command = [
            "estimate-ngram",
            "-o", str (self.ngram_order),
            "-t", self.corpus_path,
            "-wl", self.arpa_path
        ]

        self.logger.debug (u" ".join (command))

        return command

    def makeAlignerCommand (self) :
        """Build the aligner command from the provided arguments.

        Build the aligner command from the provided arguments.

        Returns:
            list: The command in subprocess list format.
        """

        command = [
            "phonetisaurus-align",
            "--input={0}".format (self.lexicon_file),
            "--ofile={0}".format (self.corpus_path),
            "--seq1_del={0}".format (str (self.seq1_del).lower ()),
            "--seq2_del={0}".format (str (self.seq2_del).lower ()),
            "--seq1_max={0}".format (str (self.seq1_max)),
            "--seq2_max={0}".format (str (self.seq2_max)),
            "--grow={0}".format (str (self.grow).lower ())
        ]

        self.logger.debug (u" ".join (command))

        return command

    def makeARPAToWFSTCommand (self) :
        """Build the ARPA to Fst conversion command.

        Build the ARPA to Fst conversion command from the provided arguments.

        Returns:
            list: The command in subprocess list format.
        """

        command = [
            "phonetisaurus-arpa2wfst",
            "--lm={0}".format (self.arpa_path),
            "--ofile={0}".format (self.model_path)
        ]

        self.logger.debug (u" ".join (command))

        return command

    def AlignLexicon (self) :
        """Align the provided input pronunciation lexicon.

        Align the provided input pronunciation lexicon according to the
        provided parameters.

        Returns:
            bool: True on success, False on failure.
        """

        aligner_command = self.makeAlignerCommand ()

        self.logger.info ("Aligning lexicon...")
        try :
            if self.verbose :
                subprocess.check_call (aligner_command)
            else :
                with open (os.devnull, "w") as devnull :
                    subprocess.check_call (
                        aligner_command,
                        stderr=devnull,
                        stdout=devnull
                    )
        except subprocess.CalledProcessError :
            self.logger.error ("Alignment failed.  Exiting.")
            sys.exit (1)

        return

    def TrainNGramModel (self) :
        """Train the joint ngram model.

        Train the joint ngram model using the selected toolkit.

        Returns:
            bool: True on success, False on failure.
        """
        joint_ngram_command = self.makeJointNgramCommand ()

        self.logger.info ("Training joint ngram model...")
        try :
            if self.verbose :
                subprocess.check_call (joint_ngram_command)
            else :
                with open (os.devnull, "w") as devnull :
                    subprocess.check_call (
                        joint_ngram_command,
                        stderr=devnull,
                        stdout=devnull
                    )
        except subprocess.CalledProcessError :
            self.logger.error ("Ngram model estimation failed.  Exiting.")
            sys.exit (1)

        return

    def ConvertARPAToWFST (self) :
        """Convert the ARPA format joint n-gram model to Fst format.

        Convert the ARPA format joint n-gram model to an equivalent Fst
        compatible with ```phonetisaurus-g2pfst```.

        Returns:
            bool: True on success, False on failure.
        """

        arpa_to_fst_command = self.makeARPAToWFSTCommand ()

        self.logger.info ("Converting ARPA format joint n-gram "
                          "model to WFST format...")
        try :
            if self.verbose :
                subprocess.check_call (arpa_to_fst_command)
            else :
                with open (os.devnull, "w") as devnull :
                    subprocess.check_call (
                        arpa_to_fst_command,
                        stderr=devnull,
                        stdout=devnull
                    )
        except subprocess.CalledProcessError :
            self.logger.error ("ARPA to WFST conversion failed.  Exiting.")
            sys.exit (1)

        return

    def TrainG2PModel (self) :
        self.checkPhonetisaurusConfig ()

        self.AlignLexicon ()
        self.TrainNGramModel ()
        self.ConvertARPAToWFST ()

        self.logger.info (
            "G2P training succeeded: \033[92m{0}\033[0m"\
            .format (self.model_path)
        )

        return

if __name__ == "__main__" :
    import sys, argparse

    example = "{0} --lexicon cmud.dic --seq2_del".format (sys.argv [0])
    parser  = argparse.ArgumentParser (description=example)
    parser.add_argument ("--lexicon", "-l", help="Training lexicon to use.",
                         required=True)
    parser.add_argument ("--dir_prefix", "-dp", help="Output directory prefix.",
                         default="train")
    parser.add_argument ("--model_prefix", "-mp", help="Output model prefix.",
                         default="model")
    parser.add_argument ("--ngram_order", "-o", help="Maximum ngram order "
                         "for joint ngram model.", type=int, default=8)
    parser.add_argument ("--seq1_del", "-s1d", help="Allow alignment deletions "
                         "in sequence one (graphemes).",
                         default=False, action="store_true")
    parser.add_argument ("--seq2_del", "-s2d", help="Allow alignment deletions "
                         "in sequence two (phonemes).",
                         default=False, action="store_true")
    parser.add_argument ("--seq1_max", "-s1m", help="Maximum subsequence "
                         "length for graphemic alignment chunks.",
                         type=int, default=2)
    parser.add_argument ("--seq2_max", "-s2m", help="Maximum subsequence "
                         "length for phonemic alignment chunks.",
                         type=int, default=2)
    parser.add_argument ("--grow", "-g", help="Allow alignment to grow maxes "
                         "for un-alignable entries.", default=False,
                         action="store_true")
    parser.add_argument ("--lm", "-lm", help="LM toolkit to use.",
                         default="mitlm")
    parser.add_argument ("--verbose", "-v", help="Verbose mode.",
                         default=False, action="store_true")
    args = parser.parse_args ()

    trainer = G2PModelTrainer (args.lexicon, **args.__dict__)
    trainer.TrainG2PModel ()
