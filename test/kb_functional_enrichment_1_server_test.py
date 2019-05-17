# -*- coding: utf-8 -*-
import csv
import os  # noqa: F401
import shutil
import time
import unittest
from configparser import ConfigParser  # py3
from os import environ

from Bio import SeqIO

from installed_clients.DataFileUtilClient import DataFileUtil
from installed_clients.GenomeAnnotationAPIClient import GenomeAnnotationAPI
from installed_clients.WorkspaceClient import Workspace as Workspace
from kb_functional_enrichment_1.Utils.FunctionalEnrichmentUtil import FunctionalEnrichmentUtil
from kb_functional_enrichment_1.authclient import KBaseAuth as _KBaseAuth
from kb_functional_enrichment_1.kb_functional_enrichment_1Impl import kb_functional_enrichment_1
from kb_functional_enrichment_1.kb_functional_enrichment_1Server import MethodContext


class kb_functional_enrichment_1Test(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        token = environ.get('KB_AUTH_TOKEN', None)
        config_file = environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('kb_functional_enrichment_1'):
            cls.cfg[nameval[0]] = nameval[1]
        # Getting username from Auth profile for token
        authServiceUrl = cls.cfg['auth-service-url']
        auth_client = _KBaseAuth(authServiceUrl)
        user_id = auth_client.get_user(token)
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = MethodContext(None)
        cls.ctx.update({'token': token,
                        'user_id': user_id,
                        'provenance': [
                            {'service': 'kb_functional_enrichment_1',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        cls.wsURL = cls.cfg['workspace-url']
        cls.wsClient = Workspace(cls.wsURL)
        cls.serviceImpl = kb_functional_enrichment_1(cls.cfg)
        cls.scratch = cls.cfg['scratch']
        cls.callback_url = os.environ['SDK_CALLBACK_URL']

        cls.fe1_runner = FunctionalEnrichmentUtil(cls.cfg)
        cls.dfu = DataFileUtil(cls.callback_url)
        cls.gaa = GenomeAnnotationAPI(cls.callback_url)
        cls.ws = Workspace(cls.wsURL, token=token)

        suffix = int(time.time() * 1000)
        cls.wsName = "test_kb_functional_enrichment_1_" + str(suffix)
        cls.wsClient.create_workspace({'workspace': cls.wsName})

        cls.prepare_data()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    @classmethod
    def prepare_data(cls):
        # upload genome object
        genome_file_name = 'Escherichia_coli_042_uid161985.faa'
        genome_file_path = os.path.join(cls.scratch, genome_file_name)
        shutil.copy(os.path.join('data', genome_file_name), genome_file_path)

        features = []
        for record in SeqIO.parse(genome_file_path, "fasta"):
            id = record.id
            sequence = str(record.seq)
            descr = record.description
            if len(sequence) <= 100:
                features.append({"id": id, "location": [["bkjg", 1, "+", 10]],
                                 "type": "CDS", "protein_translation": sequence,
                                 "aliases": [], "annotations": [], "function": descr,
                                 "ontology_terms": {"GO":
                                                    {"GO:0003677": {"id": "GO:0003677",
                                                                    "ontology_ref": "KBaseOntology/gene_ontology",
                                                                    "term_lineage": [],
                                                                    "term_name": "DNA binding",
                                                                    "evidence": []},
                                                     "GO:non_exist": {"id": "GO:non_exist",
                                                                      "ontology_ref": "KBaseOntology/gene_ontology",
                                                                      "term_lineage": [],
                                                                      "term_name": "DNA-template",
                                                                      "evidence": []}}}})

        genome_obj = {"complete": 0, "contig_ids": ["1"], "contig_lengths": [10],
                      "dna_size": 10, "domain": "Bacteria", "gc_content": 0.5,
                      "genetic_code": 11, "id": genome_file_name, "md5": "md5",
                      "num_contigs": 1, "scientific_name": genome_file_name,
                      "source": "test folder", "source_id": "noid",
                      "features": features}
        genome_obj_name = 'test_Genome'
        info = cls.gaa.save_one_genome_v1({'workspace': cls.wsName,
                                           'name': genome_obj_name,
                                           'data': genome_obj})['info']
        cls.genome_ref = str(info[6]) + "/" + str(info[0]) + "/" + str(info[4])

        # save empty genome
        genome_obj_name = 'bad_test_Genome'
        genome_obj['features'] = []
        info = cls.gaa.save_one_genome_v1({'workspace': cls.wsName,
                                           'name': genome_obj_name,
                                           'data': genome_obj})['info']
        bad_genome_ref = str(info[6]) + "/" + str(info[0]) + "/" + str(info[4])

        # upload feature set object
        test_feature_set_name = 'MyFeatureSet'
        test_feature_set_data = {'description': 'FeatureSet from DifferentialExpression',
                                 'element_ordering': ['gi|387605483|ref|YP_006094339.1|'],
                                 'elements': {'gi|387605483|ref|YP_006094339.1|': [cls.genome_ref]}}

        save_object_params = {
            'id': cls.dfu.ws_name_to_id(cls.wsName),
            'objects': [{'type': 'KBaseCollections.FeatureSet',
                         'data': test_feature_set_data,
                         'name': test_feature_set_name}]
        }

        dfu_oi = cls.dfu.save_objects(save_object_params)[0]
        cls.feature_set_ref = str(dfu_oi[6]) + '/' + str(dfu_oi[0]) + '/' + str(dfu_oi[4])

        # upload bad feature set objects
        test_feature_set_name = 'BadFeatureSet1'
        test_feature_set_data['elements']['gi|387605483|ref|YP_006094339.1|'] = [bad_genome_ref]
        save_object_params = {
            'id': cls.dfu.ws_name_to_id(cls.wsName),
            'objects': [{'type': 'KBaseCollections.FeatureSet',
                         'data': test_feature_set_data,
                         'name': test_feature_set_name}]
        }

        dfu_oi = cls.dfu.save_objects(save_object_params)[0]
        cls.bad_genome_feature_set = str(dfu_oi[6]) + '/' + str(dfu_oi[0]) + '/' + str(dfu_oi[4])

        test_feature_set_name = 'BadFeatureSet2'
        test_feature_set_data = {'description': 'FeatureSet from DifferentialExpression',
                                 'element_ordering': ['foo'],
                                 'elements': {'foo': [cls.genome_ref]}}

        save_object_params = {
            'id': cls.dfu.ws_name_to_id(cls.wsName),
            'objects': [{'type': 'KBaseCollections.FeatureSet',
                         'data': test_feature_set_data,
                         'name': test_feature_set_name}]
        }

        dfu_oi = cls.dfu.save_objects(save_object_params)[0]
        cls.bad_id_feature_set = str(dfu_oi[6]) + '/' + str(dfu_oi[0]) + '/' + str(dfu_oi[4])

    def getWsClient(self):
        return self.__class__.wsClient

    def getWsName(self):
        return self.__class__.wsName

    def getImpl(self):
        return self.__class__.serviceImpl

    def getContext(self):
        return self.__class__.ctx

    def test_bad_run_fe1_params(self):
        invalidate_input_params = {'missing_feature_set_ref': 'feature_set_ref',
                                   'workspace_name': 'workspace_name'}
        with self.assertRaisesRegex(ValueError,
                                     '"feature_set_ref" parameter is required, but missing'):
            self.getImpl().run_fe1(self.getContext(), invalidate_input_params)

        invalidate_input_params = {'feature_set_ref': 'feature_set_ref',
                                   'missing_workspace_name': 'workspace_name'}
        with self.assertRaisesRegex(ValueError,
                                     '"workspace_name" parameter is required, but missing'):
            self.getImpl().run_fe1(self.getContext(), invalidate_input_params)

        with self.assertRaisesRegex(ValueError,
                                     'No features in the referenced genome'):
            self.getImpl().run_fe1(self.getContext(), {
                'feature_set_ref': self.bad_genome_feature_set,
                'workspace_name': self.getWsName(),
                'propagation': 0,
                'filter_ref_features': 1
            })
        with self.assertRaisesRegex(ValueError,
                                     'feature ids which are not present referenced genome'):
            self.getImpl().run_fe1(self.getContext(), {
                'feature_set_ref': self.bad_id_feature_set,
                'workspace_name': self.getWsName(),
                'propagation': 0,
                'filter_ref_features': 1
            })

    def test_run_fe1(self):

        input_params = {
            'feature_set_ref': self.feature_set_ref,
            'workspace_name': self.getWsName(),
            'propagation': 0,
            'filter_ref_features': 1
        }

        result = self.getImpl().run_fe1(self.getContext(), input_params)[0]

        self.assertTrue('result_directory' in result)
        result_files = os.listdir(result['result_directory'])
        print(result_files)
        expect_result_files = ['functional_enrichment.csv']
        self.assertTrue(all(x in result_files for x in expect_result_files))

        with open(os.path.join(result['result_directory'],
                  'functional_enrichment.csv'), 'r') as f:

            self.assertEqual(2, len(f.readlines()))
            f.seek(0, 0)

            reader = csv.reader(f)
            header = next(reader)
            expected_header = ['term_id', 'term', 'ontology', 'num_in_feature_set',
                               'num_in_ref_genome', 'raw_p_value', 'adjusted_p_value']
            self.assertTrue(all(x in header for x in expected_header))

            first_row = next(reader)
            self.assertTrue(len(first_row))

        self.assertTrue(result.get('report_name'))
        self.assertTrue(result.get('report_ref'))

    def test_run_fe1_propagation(self):

        input_params = {
            'feature_set_ref': self.feature_set_ref,
            'workspace_name': self.getWsName(),
            'propagation': 1,
            'filter_ref_features': 1
        }

        result = self.getImpl().run_fe1(self.getContext(), input_params)[0]

        self.assertTrue(result.get('result_directory'))
        result_files = os.listdir(result['result_directory'])
        print(result_files)
        expect_result_files = ['functional_enrichment.csv']
        self.assertTrue(all(x in result_files for x in expect_result_files))

        with open(os.path.join(result['result_directory'],
                  'functional_enrichment.csv'), 'r') as f:

            self.assertEqual(2, len(f.readlines()))
            f.seek(0, 0)

            reader = csv.reader(f)
            header = next(reader)
            expected_header = ['term_id', 'term', 'ontology', 'num_in_feature_set',
                               'num_in_ref_genome', 'raw_p_value', 'adjusted_p_value']
            self.assertTrue(all(x in header for x in expected_header))

            first_row = next(reader)
            self.assertTrue(len(first_row))

        self.assertTrue(result.get('report_name'))
        self.assertTrue(result.get('report_ref'))
