import unittest
import os
from shared.conf import get_configuration_object
from shared.fileio import remove_rec
from shared.vgrid import vgrid_set_triggers
from shared.workflows import reset_user_workflows, WORKFLOW_PATTERN, \
    WORKFLOW_RECIPE, WORKFLOW_ANY, get_workflow_with, reset_vgrid_workflows, \
    delete_workflow, create_workflow, update_workflow

this_path = os.path.dirname(os.path.abspath(__file__))
dummy_notebook = {
    'cells':
        [
            {
                'cell_type': 'code',
                'execution_count': None,
                'metadata': {},
                'outputs': [],
                'source': []
            }
        ],
    'metadata':
        {
            'kernelspec':
                {
                    'display_name': 'Python 3',
                    'language': 'python',
                    'name': 'python3'
                },
            'language_info':
                {
                    'codemirror_mode':
                        {
                            'name': 'ipython',
                            'version': 3
                        },
                    'file_extension': '.py',
                    'mimetype': 'text/x-python',
                    'name': 'python',
                    'nbconvert_exporter': 'python',
                    'pygments_lexer': 'ipython3',
                    'version': '3.7.4'
                }
        },
    'nbformat': 4,
    'nbformat_minor': 2
}


class WorkflowsFunctionsTest(unittest.TestCase):

    def setUp(self):
        self.created_workflows = []
        self.username = 'FooBar'
        self.test_vgrid = 'unit_test_vgrid'
        self.vgrid_home = "/home/mig/state/vgrid_home/" + self.test_vgrid
        self.mrsl_home = "/home/mig/state/mrsl_files/" + self.username
        self.assertFalse(os.path.exists(self.vgrid_home))
        self.assertFalse(os.path.exists(self.mrsl_home))

        if not os.environ.get('MIG_CONF', False):
            os.environ['MIG_CONF'] = '/home/mig/mig/server/MiGserver.conf'
        self.configuration = get_configuration_object()
        self.logger = self.configuration.logger

        if not os.path.exists(self.vgrid_home):
            os.makedirs(self.vgrid_home)
        (trigger_status, trigger_msg) = vgrid_set_triggers(self.configuration,
                                                           self.test_vgrid,
                                                           [])
        if not os.path.exists(self.mrsl_home):
            os.makedirs(self.mrsl_home)

        self.assertTrue(trigger_status)

    def tearDown(self):
        if not os.environ.get('MIG_CONF', False):
            os.environ['MIG_CONF'] = '/home/mig/mig/server/MiGserver.conf'
        configuration = get_configuration_object()
        test_vgrid = 'P-Cubed'
        # Also clear vgrid_dir of any patterns and recipes
        self.assertTrue(reset_vgrid_workflows(configuration, test_vgrid))

        self.assertTrue(remove_rec(self.vgrid_home, self.configuration))
        self.assertTrue(remove_rec(self.mrsl_home, self.configuration))

    def test_create_workflow_pattern(self):
        pattern_attributes = {'name': 'my new pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **pattern_attributes)
        self.logger.info(msg)
        self.assertTrue(created)
        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_PATTERN,
                                     **pattern_attributes)
        self.assertIsNotNone(workflow)
        self.assertEqual(len(workflow), 1)
        # Strip internal attributes
        workflow[0].pop('persistence_id')
        workflow[0].pop('object_type')
        workflow[0].pop('trigger')
        self.assertDictEqual(workflow[0], pattern_attributes)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_pattern_create_with_persistence_id(self):
        pattern_attributes = {'name': 'my new pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20},
                              'persistence_id': 'persistence0123456789'}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **pattern_attributes)
        self.logger.info(msg)
        self.assertFalse(created)
        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_PATTERN,
                                     **pattern_attributes)
        self.assertIsNone(workflow)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_pattern_create_with_duplicate_name(self):
        pattern_attributes = {'name': 'my new pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **pattern_attributes)
        self.logger.info(msg)
        self.assertTrue(created)

        pattern_2_attributes = {'name': 'my new pattern',
                                'vgrid': self.test_vgrid,
                                'input_file': 'hdf5_in',
                                'trigger_paths': ['initial_data/*txt'],
                                'output': {
                                  'processed_data': 'output/*.hdf5'},
                                'recipes': ['recipe_2'],
                                'variables': {'iterations': 35}}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **pattern_2_attributes)
        self.logger.info(msg)
        self.assertFalse(created)

        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_PATTERN,
                                     **pattern_attributes)
        self.assertIsNotNone(workflow)
        self.assertEqual(len(workflow), 1)
        # Strip internal attributes
        workflow[0].pop('persistence_id')
        workflow[0].pop('object_type')
        workflow[0].pop('trigger')
        self.assertDictEqual(workflow[0], pattern_attributes)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    # def test_pattern_create_with_duplicate_attributes(self):
    #     pattern_attributes = {'name': 'my new pattern',
    #                           'vgrid': self.test_vgrid,
    #                           'input_file': 'hdf5_input',
    #                           'trigger_paths': ['initial_data/*hdf5'],
    #                           'output': {
    #                               'processed_data': 'pattern_0_output/*.hdf5'},
    #                           'recipes': ['recipe_0'],
    #                           'variables': {'iterations': 20}}
    #
    #     created, msg = create_workflow(self.configuration,
    #                                    self.username,
    #                                    workflow_type=WORKFLOW_PATTERN,
    #                                    **pattern_attributes)
    #     self.logger.info(msg)
    #     self.assertTrue(created)
    #
    #     pattern_2_attributes = {'name': 'my second pattern',
    #                             'vgrid': self.test_vgrid,
    #                             'input_file': 'hdf5_input',
    #                             'trigger_paths': ['initial_data/*hdf5'],
    #                             'output': {
    #                                 'processed_data':
    #                                     'pattern_0_output/*.hdf5'},
    #                             'recipes': ['recipe_0'],
    #                             'variables': {'iterations': 20}}
    #
    #     created, msg = create_workflow(self.configuration,
    #                                    self.username,
    #                                    workflow_type=WORKFLOW_PATTERN,
    #                                    **pattern_2_attributes)
    #     self.logger.info(msg)
    #     self.assertFalse(created)
    #
    #     workflow = get_workflow_with(self.configuration,
    #                                  client_id=self.username,
    #                                  display_safe=True,
    #                                  workflow_type=WORKFLOW_PATTERN,
    #                                  **pattern_attributes)
    #     self.assertIsNotNone(workflow)
    #     self.assertEqual(len(workflow), 1)
    #     # Strip internal attributes
    #     workflow[0].pop('persistence_id')
    #     workflow[0].pop('object_type')
    #     workflow[0].pop('trigger')
    #     self.assertDictEqual(workflow[0], pattern_attributes)
    #
    #     # Remove workflow
    #     self.assertTrue(reset_user_workflows(self.configuration,
    #                                          self.username))

    def test_create_workflow_recipe(self):
        recipe_attributes = {'name': 'my new recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'notebook.ipynb'}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **recipe_attributes)
        self.logger.info(msg)
        self.assertTrue(created)
        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_RECIPE,
                                     **recipe_attributes)
        self.assertIsNotNone(workflow)
        self.assertEqual(len(workflow), 1)
        # Strip internal attributes
        workflow[0].pop('persistence_id')
        workflow[0].pop('object_type')
        workflow[0].pop('triggers')
        self.assertDictEqual(workflow[0], recipe_attributes)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_recipe_create_with_persistence_id(self):
        recipe_attributes = {'name': 'my new recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'notebook.ipynb',
                             'persistence_id': 'persistence0123456789'}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **recipe_attributes)
        self.logger.info(msg)
        self.assertFalse(created)
        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_RECIPE,
                                     **recipe_attributes)
        self.assertIsNone(workflow)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_recipe_create_with_duplicate_name(self):
        recipe_attributes = {'name': 'my new recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'notebook.ipynb'}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **recipe_attributes)
        self.logger.info(msg)
        self.assertTrue(created)

        recipe_2_attributes = {'name': 'my new recipe',
                               'vgrid': self.test_vgrid,
                               'recipe': dummy_notebook,
                               'source': 'notebook.ipynb'}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **recipe_attributes)
        self.logger.info(msg)
        self.assertFalse(created)

        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_RECIPE,
                                     **recipe_attributes)
        self.assertIsNotNone(workflow)
        self.assertEqual(len(workflow), 1)
        # Strip internal attributes
        workflow[0].pop('persistence_id')
        workflow[0].pop('object_type')
        workflow[0].pop('triggers')
        self.assertDictEqual(workflow[0], recipe_attributes)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_create_read_delete_pattern(self):
        pattern_attributes = {'name': 'my new pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **pattern_attributes)
        self.logger.info(msg)
        self.assertTrue(created)

        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_PATTERN,
                                     **pattern_attributes)
        self.assertIsNot(workflow, False)
        self.assertEqual(len(workflow), 1)
        # Strip internal attributes
        persistence_id = workflow[0].pop('persistence_id')
        workflow[0].pop('object_type')
        workflow[0].pop('trigger')
        self.assertDictEqual(workflow[0], pattern_attributes)

        # TODO, validate it has the expected attributes
        delete_attributes = {
            'vgrid': self.test_vgrid,
            'persistence_id': persistence_id
        }

        deleted, msg = delete_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **delete_attributes)

        self.logger.info(msg)
        self.assertTrue(deleted)

        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_PATTERN,
                                     **pattern_attributes)
        self.assertIsNone(workflow)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_create_read_delete_recipe(self):
        recipe_attributes = {'name': 'my new recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'notebook.ipynb'}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **recipe_attributes)
        self.logger.info(msg)
        self.assertTrue(created)

        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_RECIPE,
                                     **recipe_attributes)
        self.assertIsNot(workflow, False)
        self.assertEqual(len(workflow), 1)
        # Strip internal attributes
        persistence_id = workflow[0].pop('persistence_id')
        workflow[0].pop('object_type')
        workflow[0].pop('triggers')
        self.assertDictEqual(workflow[0], recipe_attributes)

        # TODO, validate it has the expected attributes
        delete_attributes = {'vgrid': self.test_vgrid,
                             'persistence_id': persistence_id}

        deleted, msg = delete_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **delete_attributes)
        self.logger.info(msg)
        self.assertTrue(deleted)

        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_RECIPE,
                                     **recipe_attributes)
        self.assertIsNone(workflow)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_update_pattern(self):
        pattern_attributes = {'name': 'my new pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}

        created, persistence_id = create_workflow(
            self.configuration,
            self.username,
            workflow_type=WORKFLOW_PATTERN,
            **pattern_attributes
        )
        self.logger.info(persistence_id)
        self.assertTrue(created)
        new_attributes = {'name': 'Updated named',
                          'vgrid': self.test_vgrid,
                          'persistence_id': persistence_id}

        updated, msg = update_workflow(
            self.configuration,
            self.username,
            workflow_type=WORKFLOW_PATTERN,
            **new_attributes
        )
        self.logger.info(msg)
        self.assertTrue(updated)

        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_PATTERN,
                                     **{'persistence_id': persistence_id})
        self.assertEqual(len(workflow), 1)
        self.assertEqual(workflow[0]['name'], new_attributes['name'])

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_update_pattern_without_persistence_id(self):
        pattern_attributes = {'name': 'my new pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}

        created, persistence_id = create_workflow(
            self.configuration,
            self.username,
            workflow_type=WORKFLOW_PATTERN,
            **pattern_attributes
        )
        self.logger.info(persistence_id)
        self.assertTrue(created)
        new_attributes = {'name': 'Updated named',
                          'vgrid': self.test_vgrid}

        updated, msg = update_workflow(
            self.configuration,
            self.username,
            workflow_type=WORKFLOW_PATTERN,
            **new_attributes
        )
        self.logger.info(msg)
        self.assertFalse(updated)

        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_PATTERN,
                                     **{'persistence_id': persistence_id})
        self.assertEqual(len(workflow), 1)
        self.assertEqual(workflow[0]['name'], pattern_attributes['name'])

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_update_recipe(self):
        recipe_attributes = {'name': 'my new recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'notebook.ipynb'}

        created, persistence_id = create_workflow(
            self.configuration,
            self.username,
            workflow_type=WORKFLOW_RECIPE,
            **recipe_attributes
        )

        self.assertTrue(created)
        new_attributes = {'name': 'Updated named',
                          'vgrid': self.test_vgrid,
                          'persistence_id': persistence_id}
        # Try update without persistence_id
        updated, msg = update_workflow(
            self.configuration,
            self.username,
            workflow_type=WORKFLOW_RECIPE,
            **new_attributes
        )
        self.logger.info(msg)
        self.assertTrue(updated)

        workflow = get_workflow_with(
            self.configuration,
            client_id=self.username,
            display_safe=True,
            workflow_type=WORKFLOW_RECIPE,
            **{'persistence_id': persistence_id}
        )
        self.assertEqual(len(workflow), 1)
        self.assertEqual(workflow[0]['name'], new_attributes['name'])

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_update_recipe_without_persistence_id(self):
        recipe_attributes = {'name': 'my new recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'notebook.ipynb'}

        created, persistence_id = create_workflow(
            self.configuration,
            self.username,
            workflow_type=WORKFLOW_RECIPE,
            **recipe_attributes
        )

        self.assertTrue(created)
        new_attributes = {'name': 'Updated named',
                          'vgrid': self.test_vgrid}
        # Try update without persistence_id
        updated, msg = update_workflow(
            self.configuration,
            self.username,
            workflow_type=WORKFLOW_RECIPE,
            **new_attributes
        )
        self.logger.info(msg)
        self.assertFalse(updated)

        workflow = get_workflow_with(
            self.configuration,
            client_id=self.username,
            display_safe=True,
            workflow_type=WORKFLOW_RECIPE,
            **{'persistence_id': persistence_id}
        )
        self.assertEqual(len(workflow), 1)
        self.assertEqual(workflow[0]['name'], recipe_attributes['name'])

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_clear_user_worklows(self):
        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

        pattern_attributes = {'name': 'foobarpattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}
        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **pattern_attributes)
        self.assertTrue(created)

        recipe_attributes = {'name': 'my new recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': {'exec': 'code'},
                             'source': 'print("Hello World")'}
        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **recipe_attributes)
        self.assertTrue(created)

        # Get every workflow in vgrid
        workflows = get_workflow_with(
            self.configuration,
            client_id=self.username,
            display_safe=True,
            workflow_type=WORKFLOW_ANY,
            **{'vgrid': self.test_vgrid}
        )
        self.logger.info("Got workflow %s" % workflows)
        self.assertIsNotNone(workflows)
        # Verify that the created objects exist
        self.assertEqual(len(workflows), 2)
        for workflow in workflows:
            workflow.pop('persistence_id')
            if workflow['object_type'] == WORKFLOW_PATTERN:
                workflow.pop('object_type')
                workflow.pop('trigger')
                self.assertDictEqual(workflow, pattern_attributes)
                continue

            if workflow['object_type'] == WORKFLOW_RECIPE:
                workflow.pop('object_type')
                workflow.pop('triggers')
                self.assertDictEqual(workflow, recipe_attributes)

        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

        workflows = get_workflow_with(
            self.configuration,
            client_id=self.username,
            display_safe=True,
            workflow_type=WORKFLOW_ANY,
            **{'vgrid': self.test_vgrid}
        )
        self.assertIsNone(workflows)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_delete_pattern(self):
        pattern_attributes = {'name': 'pattern to delete',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **pattern_attributes)
        self.logger.info(msg)
        self.assertTrue(created)
        persistence_id = msg

        deletion_attributes = {
            'persistence_id': persistence_id,
            'vgrid': self.test_vgrid
        }

        deleted, msg = delete_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **deletion_attributes)

        self.logger.info(msg)
        self.assertTrue(deleted)

        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     **deletion_attributes)

        self.assertIsNone(workflow)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_delete_pattern_without_persistence_id(self):
        pattern_attributes = {'name': 'pattern to delete',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **pattern_attributes)
        self.logger.info(msg)
        self.assertTrue(created)
        persistence_id = msg

        deletion_attributes = {
            'vgrid': self.test_vgrid
        }

        deleted, msg = delete_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **deletion_attributes)

        self.logger.info(msg)
        self.assertFalse(deleted)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_delete_recipe(self):
        recipe_attributes = {'name': 'recipe to delete',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'notebook.ipynb'}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **recipe_attributes)
        self.logger.info(msg)
        self.assertTrue(created)
        persistence_id = msg

        deletion_attributes = {
            'persistence_id': persistence_id,
            'vgrid': self.test_vgrid
        }

        deleted, msg = delete_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **deletion_attributes)

        self.logger.info(msg)
        self.assertTrue(deleted)

        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     **deletion_attributes)

        self.assertIsNone(workflow)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_delete_recipe_without_persistence_id(self):
        recipe_attributes = {'name': 'recipe to delete',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'notebook.ipynb'}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **recipe_attributes)
        self.logger.info(msg)
        self.assertTrue(created)
        persistence_id = msg

        deletion_attributes = {
            'vgrid': self.test_vgrid
        }

        deleted, msg = delete_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **deletion_attributes)

        self.logger.info(msg)
        self.assertFalse(deleted)

        # Remove workflow
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

    def test_workflow_trigger_creation_from_pattern(self):
        recipe_attributes = {'name': 'trigger creation from pattern recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'notebook.ipynb'}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **recipe_attributes)
        self.logger.info(msg)
        self.assertTrue(created)

        pattern_attributes = {'name': 'trigger creation from pattern pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': [
                                  'trigger creation from pattern recipe'],
                              'variables': {'iterations': 20}}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **pattern_attributes)
        self.logger.info(msg)
        self.assertTrue(created)

        recipes = get_workflow_with(self.configuration,
                                    client_id=self.username,
                                    display_safe=True,
                                    workflow_type=WORKFLOW_RECIPE,
                                    **recipe_attributes)
        self.assertIsNotNone(recipes)
        self.assertEqual(len(recipes), 1)

        patterns = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_PATTERN,
                                     **pattern_attributes)
        self.assertIsNotNone(patterns)
        self.assertEqual(len(patterns), 1)

        self.assertIn('triggers', recipes[0])
        self.assertIn('trigger', patterns[0])

        pattern_trigger = patterns[0]['trigger']
        recipe_triggers = recipes[0]['triggers']

        self.assertIsNotNone(pattern_trigger)
        self.assertIsNotNone(recipe_triggers)
        self.assertEqual(len(recipe_triggers), 1)

        recipe_trigger = recipe_triggers[recipe_triggers.keys()[0]]

        self.assertDictEqual(pattern_trigger, recipe_trigger)

        # Remove workflow
        self.assertTrue(
            reset_user_workflows(self.configuration, self.username)
        )

    def test_workflow_trigger_creation_from_recipe(self):
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

        pattern_attributes = {'name': 'trigger creation from recipe pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': [
                                  'trigger creation from recipe recipe'],
                              'variables': {'iterations': 20}}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **pattern_attributes)
        self.logger.info(msg)
        self.assertTrue(created)

        recipe_attributes = {'name': 'trigger creation from recipe recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'print("Hello World")'}

        created, msg = create_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_RECIPE,
                                       **recipe_attributes)
        self.logger.info(msg)
        self.assertTrue(created)

        recipes = get_workflow_with(self.configuration,
                                    client_id=self.username,
                                    display_safe=True,
                                    workflow_type=WORKFLOW_RECIPE,
                                    **recipe_attributes)
        self.assertIsNotNone(recipes)
        self.assertEqual(len(recipes), 1)

        patterns = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
                                     workflow_type=WORKFLOW_PATTERN,
                                     **pattern_attributes)
        self.assertIsNotNone(patterns)
        self.assertEqual(len(patterns), 1)

        self.assertIn('triggers', recipes[0])
        self.assertIn('trigger', patterns[0])

        pattern_trigger = patterns[0]['trigger']
        recipe_triggers = recipes[0]['triggers']

        self.assertIsNotNone(pattern_trigger)
        self.assertIsNotNone(recipe_triggers)
        self.assertEqual(len(recipe_triggers), 1)

        recipe_trigger = recipe_triggers[recipe_triggers.keys()[0]]

        self.assertDictEqual(pattern_trigger, recipe_trigger)

        # Remove workflow
        self.assertTrue(
            reset_user_workflows(self.configuration, self.username)
        )

    def test_recipe_pattern_association_creation_pattern_first(self):
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

        pattern_attributes = {'name': 'association test pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['association test recipe'],
                              'variables': {'iterations': 20}}

        created, pattern_id = create_workflow(self.configuration,
                                              self.username,
                                              workflow_type=WORKFLOW_PATTERN,
                                              **pattern_attributes)
        self.logger.info(pattern_id)
        self.assertTrue(created)

        recipe_attributes = {'name': 'association test recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'print("Hello World")'}

        created, recipe_id = create_workflow(self.configuration,
                                             self.username,
                                             workflow_type=WORKFLOW_RECIPE,
                                             **recipe_attributes)
        self.logger.info(recipe_id)
        self.assertTrue(created)

        recipes = get_workflow_with(self.configuration,
                                    client_id=self.username,
                                    workflow_type=WORKFLOW_RECIPE,
                                    **recipe_attributes)
        self.assertIsNotNone(recipes)
        self.assertEqual(len(recipes), 1)
        self.assertIn('associated_patterns', recipes[0])
        self.assertEqual(len(recipes[0]['associated_patterns']), 1)
        self.assertEqual(recipes[0]['associated_patterns'][0], pattern_id)

        # Remove workflow
        self.assertTrue(
            reset_user_workflows(self.configuration, self.username)
        )

    def test_recipe_pattern_association_creation_recipe_first(self):
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

        recipe_attributes = {'name': 'association test recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'print("Hello World")'}

        created, recipe_id = create_workflow(self.configuration,
                                             self.username,
                                             workflow_type=WORKFLOW_RECIPE,
                                             **recipe_attributes)
        self.logger.info(recipe_id)
        self.assertTrue(created)

        pattern_attributes = {'name': 'association test pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['association test recipe'],
                              'variables': {'iterations': 20}}

        created, pattern_id = create_workflow(self.configuration,
                                              self.username,
                                              workflow_type=WORKFLOW_PATTERN,
                                              **pattern_attributes)
        self.logger.info(pattern_id)
        self.assertTrue(created)

        recipes = get_workflow_with(self.configuration,
                                    client_id=self.username,
                                    workflow_type=WORKFLOW_RECIPE,
                                    **recipe_attributes)
        self.assertIsNotNone(recipes)
        self.assertEqual(len(recipes), 1)
        self.assertIn('associated_patterns', recipes[0])
        self.assertEqual(len(recipes[0]['associated_patterns']), 1)
        self.assertEqual(recipes[0]['associated_patterns'][0], pattern_id)

        # Remove workflow
        self.assertTrue(
            reset_user_workflows(self.configuration, self.username)
        )

    def test_recipe_pattern_association_deletion(self):
        self.assertTrue(reset_user_workflows(self.configuration,
                                             self.username))

        pattern_attributes = {'name': 'association test pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['association test recipe'],
                              'variables': {'iterations': 20}}

        created, pattern_id = create_workflow(self.configuration,
                                              self.username,
                                              workflow_type=WORKFLOW_PATTERN,
                                              **pattern_attributes)
        self.logger.info(pattern_id)
        self.assertTrue(created)

        recipe_attributes = {'name': 'association test recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': dummy_notebook,
                             'source': 'print("Hello World")'}

        created, recipe_id = create_workflow(self.configuration,
                                             self.username,
                                             workflow_type=WORKFLOW_RECIPE,
                                             **recipe_attributes)
        self.logger.info(recipe_id)
        self.assertTrue(created)

        recipes = get_workflow_with(self.configuration,
                                    client_id=self.username,
                                    workflow_type=WORKFLOW_RECIPE,
                                    **recipe_attributes)
        self.assertIsNotNone(recipes)
        self.assertEqual(len(recipes), 1)
        self.assertIn('associated_patterns', recipes[0])
        self.assertEqual(len(recipes[0]['associated_patterns']), 1)
        self.assertEqual(recipes[0]['associated_patterns'][0], pattern_id)

        deletion_attributes = {
            'persistence_id': pattern_id,
            'vgrid': self.test_vgrid
        }

        deleted, msg = delete_workflow(self.configuration,
                                       self.username,
                                       workflow_type=WORKFLOW_PATTERN,
                                       **deletion_attributes)

        self.logger.info(msg)
        self.assertTrue(deleted)

        recipes = get_workflow_with(self.configuration,
                                    client_id=self.username,
                                    workflow_type=WORKFLOW_RECIPE,
                                    **recipe_attributes)
        self.assertIsNotNone(recipes)
        self.assertEqual(len(recipes), 1)
        self.assertIn('associated_patterns', recipes[0])
        self.assertEqual(len(recipes[0]['associated_patterns']), 0)

        # Remove workflow
        self.assertTrue(
            reset_user_workflows(self.configuration, self.username)
        )

if __name__ == '__main__':
    unittest.main()
