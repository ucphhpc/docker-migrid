import shared.returnvalues as returnvalues
from shared.init import initialize_main_variables
from shared.functional import validate_input_and_cert
from shared.safeinput import REJECT_UNSET
from shared.workflows import scrape_for_workflow_objects
from shared.serial import loads

CELL_TYPE, CODE, SOURCE = 'cell_type', 'code', 'source'


def signature():
    """Signature of the main function"""

    defaults = {
        'vgrid_name': REJECT_UNSET,
        'wf_notebook': '',
        'wf_notebookfilename': REJECT_UNSET,
    }
    return ['registernotebook', defaults]


def main(client_id, user_arguments_dict):
    (configuration, logger, output_objects, op_name) = \
        initialize_main_variables(client_id, op_header=False)

    logger.debug('user_arguments_dict: \n%s' % user_arguments_dict)

    defaults = signature()[1]

    vgrid_name, note_book_name = 'vgrid_name', 'wf_notebookfilename'

    # put filename in list
    user_arguments_dict[note_book_name] = [user_arguments_dict[note_book_name]]

    (validate_status, accepted) = validate_input_and_cert(
        user_arguments_dict, defaults, output_objects, client_id,
        configuration, allow_rejects=False,)

    vgrid = accepted[vgrid_name][-1]
    name = accepted[note_book_name][-1]
    # TODO, validate that the vgrid is actually accessible by the user
    # I.e. that he is a member/owner and has write access to it.
    # else we shouldn't allow that the creation of .workflow_patterns_home
    # for instance.

    # TODO get this loading in proper strings, not unicode,
    notebook = loads(accepted["wf_notebook"][-1], serializer='json')
    if not isinstance(notebook, dict):
        output_objects.append({'object_type': 'error_text', 'text':
            'Notebook is not formatted correctly'})

    metadata = notebook['metadata']

    # Check notebook is in python
    if metadata['kernelspec']['language'].encode('ascii') \
            != 'python'.encode('ascii'):
        output_objects.append({'object_type': 'error_text', 'text':
            'Notebook is not written in python, instead is %s'
            % metadata['kernelspec']['language'].encode('ascii')})

    output_objects.append({'object_type': 'text', 'text':
        'Registering JupyetLab Notebook and attempting to scrape valid '
        'workflow patterns and recipes...'})

    status, msg = scrape_for_workflow_objects(
        configuration, client_id, vgrid, notebook, name)

    output_objects.append({'object_type': 'text', 'text':msg})

    output_objects.append({'object_type': 'text', 'text':
        'Finished scraping notebook'})

    return (output_objects, returnvalues.OK)
