import unittest
import os
from shared.pwhash import generate_random_ascii
from shared.conf import get_configuration_object
from shared.validstring import possible_workflow_session_id
from shared.workflows import touch_workflow_sessions_db, \
    load_workflow_sessions_db, create_workflow_session_id, \
    delete_workflow_sessions_db, new_workflow_session_id, \
    delete_workflow_session_id

this_path = os.path.dirname(os.path.abspath(__file__))


class WorkflowJSONInterfaceTest(unittest.TestCase):

    def setUp(self):
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


    # def test_create_workflow(self):
    #     self.assertTrue(True)
    #
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
