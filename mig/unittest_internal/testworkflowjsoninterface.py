import unittest
import os
from shared.pwhash import generate_random_ascii
from shared.conf import get_configuration_object
from shared.validstring import possible_workflow_session_id
from shared.workflows import touch_workflow_sessions_db, \
    load_workflow_sessions_db, create_workflow_session_id, \
    delete_workflow_sessions_db, new_workflow_session_id, \
    delete_workflow_session_id, reset_user_workflows, \
    WORKFLOW_PATTERN, WORKFLOW_RECIPE, WORKFLOW_ANY, get_workflow_with, \
    reset_vgrid_workflows, delete_workflow
from shared.functionality.workflowjsoninterface import workflow_api_create, \
    workflow_api_delete, workflow_api_read, workflow_api_update

this_path = os.path.dirname(os.path.abspath(__file__))


class WorkflowJSONInterfaceSessionIDTest(unittest.TestCase):

    def setUp(self):
        if not os.environ.get('MIG_CONF', False):
            os.environ['MIG_CONF'] = '/home/mig/mig/server/MiGserver.conf'
        self.configuration = get_configuration_object()
        self.configuration.workflows_db = os.path.join(this_path,
                                                       'test_sessions_db')

    def tearDown(self):
        if not os.environ.get('MIG_CONF', False):
            os.environ['MIG_CONF'] = '/home/mig/mig/server/MiGserver.conf'
        configuration = get_configuration_object()
        configuration.workflows_db = os.path.join(this_path,
                                                  'test_sessions_db')
        delete_workflow_sessions_db(configuration)

    def test_workflow_session_id(self):
        wrong_session_id = generate_random_ascii(64, 'ghijklmn')
        self.assertFalse(possible_workflow_session_id(self.configuration,
                                                      wrong_session_id))
        session_id = new_workflow_session_id()
        self.assertTrue(possible_workflow_session_id(self.configuration,
                                                     session_id))

    def test_create_session_id(self):
        self.assertTrue(touch_workflow_sessions_db(self.configuration,
                                                   force=True
                                                   ))
        self.assertDictEqual(load_workflow_sessions_db(self.configuration), {})
        client_id = 'FooBar'
        workflow_session_id = create_workflow_session_id(self.configuration,
                                                         client_id)
        new_state = {workflow_session_id: {'owner': client_id}}
        new_db = load_workflow_sessions_db(self.configuration)
        self.assertEqual(new_db, new_state)
        self.assertTrue(delete_workflow_sessions_db(self.configuration))

    def test_delete_session_id(self):
        # Create
        self.assertTrue(touch_workflow_sessions_db(self.configuration,
                                                   force=True))
        client_id = 'FooBar'
        workflow_session_id = create_workflow_session_id(self.configuration,
                                                         client_id)
        new_state = {workflow_session_id: {'owner': client_id}}
        new_db = load_workflow_sessions_db(self.configuration)
        self.assertEqual(new_db, new_state)

        # Fail to remove non existing id
        self.assertFalse(delete_workflow_session_id(self.configuration,
                                                    new_workflow_session_id()))
        # Delete new_state
        self.assertTrue(delete_workflow_session_id(self.configuration,
                                                   workflow_session_id))
        self.assertEqual(load_workflow_sessions_db(self.configuration), {})
        # Delete the DB
        self.assertTrue(delete_workflow_sessions_db(self.configuration))


class WorkflowJSONInterfaceAPIFunctionsTest(unittest.TestCase):

    def setUp(self):
        self.created_workflows = []
        self.username = 'FooBar'
        self.test_vgrid = 'P-Cubed'
        if not os.environ.get('MIG_CONF', False):
            os.environ['MIG_CONF'] = '/home/mig/mig/server/MiGserver.conf'
        self.configuration = get_configuration_object()
        self.logger = self.configuration.logger
        self.configuration.workflows_db = os.path.join(this_path,
                                                       'test_sessions_db')
        touch_workflow_sessions_db(self.configuration, force=True)
        self.session_id = create_workflow_session_id(self.configuration,
                                                     self.username)
        self.assertIsNot(self.session_id, False)
        self.assertIsNotNone(self.session_id)

        self.workflow_sessions_db = load_workflow_sessions_db(
            self.configuration)
        self.assertIn(self.session_id, self.workflow_sessions_db)
        self.workflow_session = self.workflow_sessions_db.get(self.session_id,
                                                              None)
        self.assertIsNotNone(self.workflow_session)

    def tearDown(self):
        if not os.environ.get('MIG_CONF', False):
            os.environ['MIG_CONF'] = '/home/mig/mig/server/MiGserver.conf'
        configuration = get_configuration_object()
        test_vgrid = 'P-Cubed'
        configuration.workflows_db = os.path.join(this_path,
                                                  'test_sessions_db')
        self.assertTrue(delete_workflow_sessions_db(configuration))
        # Also clear vgrid_dir of any patterns and recipes
        self.assertTrue(reset_vgrid_workflows(configuration, test_vgrid))

    def test_create_workflow_pattern(self):
        pattern_attributes = {'name': 'my new pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}

        created, msg = workflow_api_create(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_PATTERN,
                                           **pattern_attributes)
        self.logger.info(msg)
        self.assertTrue(created)
        workflow = get_workflow_with(self.configuration,
                                     client_id=self.username,
                                     display_safe=True,
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

    def test_create_workflow_recipe(self):
        recipe_attributes = {'name': 'my new recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': {'exec': 'code'},
                             'source': 'print("Hello World")'}

        created, msg = workflow_api_create(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_RECIPE,
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

        created, msg = workflow_api_create(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_PATTERN,
                                           **pattern_attributes)
        self.logger.info(msg)
        self.assertTrue(created)

        workflow = workflow_api_read(self.configuration,
                                     self.workflow_session,
                                     WORKFLOW_PATTERN,
                                     **pattern_attributes)
        self.assertIsNot(workflow, False)
        self.assertEqual(len(workflow), 1)
        # Strip internal attributes
        persistence_id = workflow[0].pop('persistence_id')
        workflow[0].pop('object_type')
        workflow[0].pop('trigger')
        self.assertDictEqual(workflow[0], pattern_attributes)

        # TODO, validate it has the expected attributes
        delete_attributes = {'vgrid': self.test_vgrid,
                             'persistence_id': persistence_id}

        deleted, msg = workflow_api_delete(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_PATTERN,
                                           **delete_attributes)
        self.logger.info(msg)
        self.assertTrue(deleted)

        workflow = workflow_api_read(self.configuration,
                                     self.workflow_session,
                                     WORKFLOW_PATTERN,
                                     **pattern_attributes)
        self.assertIsNone(workflow)

    def test_create_read_delete_recipe(self):
        recipe_attributes = {'name': 'my new recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': {'exec': 'code'},
                             'source': 'print("Hello World")'}

        created, msg = workflow_api_create(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_RECIPE,
                                           **recipe_attributes)
        self.logger.info(msg)
        self.assertTrue(created)

        workflow = workflow_api_read(self.configuration,
                                     self.workflow_session,
                                     WORKFLOW_RECIPE,
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

        deleted, msg = workflow_api_delete(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_RECIPE,
                                           **delete_attributes)
        self.logger.info(msg)
        self.assertTrue(deleted)

        workflow = workflow_api_read(self.configuration,
                                     self.workflow_session,
                                     WORKFLOW_RECIPE,
                                     **recipe_attributes)
        self.assertIsNone(workflow)

    def test_update_pattern(self):
        pattern_attributes = {'name': 'my new pattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}

        created, persistence_id = workflow_api_create(self.configuration,
                                                      self.workflow_session,
                                                      WORKFLOW_PATTERN,
                                                      **pattern_attributes)
        self.logger.info(persistence_id)
        self.assertTrue(created)
        new_attributes = {'name': 'Updated named',
                          'vgrid': self.test_vgrid,
                          'persistence_id': persistence_id}

        # TODO Try update without persistence_id
        updated, msg = workflow_api_update(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_PATTERN,
                                           **new_attributes)
        self.logger.info(msg)
        self.assertTrue(updated)

        workflow = workflow_api_read(self.configuration,
                                     self.workflow_session,
                                     WORKFLOW_PATTERN,
                                     **{'persistence_id': persistence_id})
        self.assertEqual(len(workflow), 1)
        self.assertEqual(workflow[0]['name'], new_attributes['name'])

    def test_update_recipe(self):
        recipe_attributes = {'name': 'my new recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': {'exec': 'code'},
                             'source': 'print("Hello World")'}

        created, persistence_id = workflow_api_create(self.configuration,
                                                      self.workflow_session,
                                                      WORKFLOW_RECIPE,
                                                      **recipe_attributes)
        self.assertTrue(created)
        new_attributes = {'name': 'Updated named',
                          'vgrid': self.test_vgrid,
                          'persistence_id': persistence_id}
        # TODO Try update without persistence_id
        updated, msg = workflow_api_update(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_RECIPE,
                                           **new_attributes)
        self.logger.info(msg)
        self.assertTrue(updated)

        workflow = workflow_api_read(self.configuration,
                                     self.workflow_session,
                                     WORKFLOW_RECIPE,
                                     **{'persistence_id': persistence_id})
        self.assertEqual(len(workflow), 1)
        self.assertEqual(workflow[0]['name'], new_attributes['name'])

    def test_clear_user_worklows(self):
        # Create dummy workflows
        pattern_attributes = {'name': 'foobarpattern',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}
        created, msg = workflow_api_create(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_PATTERN,
                                           **pattern_attributes)
        self.assertTrue(created)

        recipe_attributes = {'name': 'my new recipe',
                             'vgrid': self.test_vgrid,
                             'recipe': {'exec': 'code'},
                             'source': 'print("Hello World")'}
        created, msg = workflow_api_create(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_RECIPE,
                                           **recipe_attributes)
        self.assertTrue(created)

        # Get every workflow in vgrid
        workflows = workflow_api_read(self.configuration,
                                      self.workflow_session,
                                      WORKFLOW_ANY,
                                      **{'vgrid': self.test_vgrid})
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

        no_workflows = workflow_api_read(self.configuration,
                                         self.workflow_session,
                                         WORKFLOW_ANY,
                                         **{'vgrid': self.test_vgrid})
        self.assertIsNone(no_workflows)

    def test_delete_pattern(self):
        pattern_attributes = {'name': 'pattern to delete',
                              'vgrid': self.test_vgrid,
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}

        created, msg = workflow_api_create(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_PATTERN,
                                           **pattern_attributes)
        self.logger.info(msg)
        self.assertTrue(created)
        persistence_id = msg

        deletion_attributes = {
            'persistence_id': persistence_id,
            'vgrid': self.test_vgrid
        }

        deleted, msg = workflow_api_delete(self.configuration,
                                           self.workflow_session,
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

    def test_delete_recipe(self):
        recipe_attributes = {'name': 'recipe to delete',
                             'vgrid': self.test_vgrid,
                             'recipe': {'exec': 'code'},
                             'source': 'print("Hello World")'}

        created, msg = workflow_api_create(self.configuration,
                                           self.workflow_session,
                                           WORKFLOW_RECIPE,
                                           **recipe_attributes)
        self.logger.info(msg)
        self.assertTrue(created)
        persistence_id = msg

        deletion_attributes = {
            'persistence_id': persistence_id,
            'vgrid': self.test_vgrid
        }

        deleted, msg = workflow_api_delete(self.configuration,
                                           self.workflow_session,
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

if __name__ == '__main__':
    unittest.main()
