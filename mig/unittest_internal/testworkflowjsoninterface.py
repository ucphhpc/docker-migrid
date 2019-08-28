import unittest
import os
from shared.pwhash import generate_random_ascii
from shared.conf import get_configuration_object
from shared.validstring import possible_workflow_session_id
from shared.workflows import touch_workflow_sessions_db, \
    load_workflow_sessions_db, create_workflow_session_id, \
    delete_workflow_sessions_db, new_workflow_session_id, \
    delete_workflow_session_id
from shared.functionality.workflowjsoninterface import WORKFLOW_PATTERN,\
    workflow_api_create, workflow_api_delete

this_path = os.path.dirname(os.path.abspath(__file__))


class WorkflowJSONInterfaceSessionIDTest(unittest.TestCase):

    def setUp(self):
        if not os.environ.get('MIG_CONF', False):
            os.environ['MIG_CONF'] = '/home/mig/mig/server/MiGserver.conf'
        self.configuration = get_configuration_object()

    def tearDown(self):
        pass

    def test_workflow_session_id(self):
        wrong_session_id = generate_random_ascii(64, 'ghijklmn')
        self.assertFalse(possible_workflow_session_id(self.configuration,
                                                      wrong_session_id))
        session_id = new_workflow_session_id()
        self.assertTrue(possible_workflow_session_id(self.configuration,
                                                     session_id))

    def test_create_session_id(self):
        self.configuration.workflows_db = os.path.join(this_path,
                                                       'test_sessions_db')
        self.assertTrue(touch_workflow_sessions_db(self.configuration,
                                                   force=True
                                                   ))
        self.assertDictEqual(load_workflow_sessions_db(self.configuration), {})
        client_id = None
        workflow_session_id = create_workflow_session_id(self.configuration,
                                                         client_id)
        new_state = {workflow_session_id: {'owner': client_id}}
        new_db = load_workflow_sessions_db(self.configuration)
        self.assertEqual(new_db, new_state)
        self.assertTrue(delete_workflow_sessions_db(self.configuration))

    def test_delete_session_id(self):
        self.configuration.workflows_db = os.path.join(this_path,
                                                       'test_sessions_db')
        # Create
        self.assertTrue(touch_workflow_sessions_db(self.configuration,
                                                   force=True))
        client_id = None
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
        self.username = 'FooBar'
        if not os.environ.get('MIG_CONF', False):
            os.environ['MIG_CONF'] = '/home/mig/mig/server/MiGserver.conf'
        self.configuration = get_configuration_object()
        self.configuration.workflows_db = os.path.join(this_path,
                                                       'test_sessions_db')
        touch_workflow_sessions_db(self.configuration, force=True)
        self.session_id = create_workflow_session_id(self.configuration,
                                                     self.username)
        self.assertIsNot(self.session_id, False)
        self.assertIsNotNone(self.session_id)

    def tearDown(self):
        if not os.environ.get('MIG_CONF', False):
            os.environ['MIG_CONF'] = '/home/mig/mig/server/MiGserver.conf'
        delete_workflow_sessions_db(get_configuration_object())

    def test_create_workflow_pattern(self):
        pattern_attributes = {'name': 'my new pattern',
                              'vgrids': 'P-Cubed',
                              'input_file': 'hdf5_input',
                              'trigger_paths': ['initial_data/*hdf5'],
                              'output': {
                                  'processed_data': 'pattern_0_output/*.hdf5'},
                              'recipes': ['recipe_0'],
                              'variables': {'iterations': 20}}
        print(self.session_id)
        workflow, msg = workflow_api_create(self.configuration,
                                            self.session_id,
                                            WORKFLOW_PATTERN,
                                            **pattern_attributes)
        print(workflow, msg)
        ok, msg = workflow_api_delete(self.configuration,
                                      self.session_id,
                                      WORKFLOW_PATTERN,
                                      **pattern_attributes)
        print(ok)
        print(msg)

    # def test_create_workflow_recipe(self):
    #     workflow = create_workflow(self.configuration, self.username,
    #                                )
    # def test_read_workflow(self):
    #     self.assertTrue(True)
    #
    # def test_update_workflow(self):
    #     self.assertTrue(True)
    #
    # def test_delete_workflow(self):
    #     self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
