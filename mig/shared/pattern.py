
DEFAULT_JOB_FILE_INPUT = 'wf_job.ipynb'
DEFAULT_JOB_FILE_OUTPUT = 'wf_job_output.ipynb'


class Pattern:
    # Could make name optional, but I think its clearer to make it mandatory
    def __init__(self, name):
        self.name = name
        self.input_file = None
        self.trigger_paths = []
        self.outputs = {}
        self.recipes = []
        self.variables = {}

    def integrity_check(self):
        warning = ''
        # NOTE, you shouldn't do an identity comparison for 'None' valued in logical comparisons
        # Use the fact that in logical comparisons None is evaluated the same as False.
        # So "if not variable:" gives the same behaviour and have a wider coverage.
        if self.input_file is None:
            return (False, "An input file must be defined. This is the file "
                           "that is used to trigger any processing and can be "
                           "defined using the methods '.add_single_input' or "
                           "'add_multiple_input")
        # NOTE, as per https://pep8.org/
            # For sequences, (strings, lists, tuples), use the fact that empty sequences are false:

            # Yes:

            # if not seq:
            # if seq:

            # No:

            # if len(seq):
            # if not len(seq):
        # Therefore you should simply these and the related ones to
        # if not self.trigger_paths:
        if len(self.trigger_paths) == 0:
            return (False, "At least one input path must be defined. This is "
                           "the path to the file that is used to trigger any "
                           "processing and can be defined using the methods "
                           "'.add_single_input' or 'add_multiple_input")
        if len(self.outputs) == 0:
            warning += '\n No output has been set, meaning no resulting ' \
                       'data will be copied back into the vgrid. ANY OUTPUT ' \
                       'WILL BE LOST.'
        if len(self.recipes) == 0:
            return (False, "No recipes have been defined")
        return (True, warning)

    def add_single_input(self, input_file, regex_path, output_path=None):
        if len(self.trigger_paths) == 0:
            self.input_file = input_file
            self.trigger_paths = [regex_path]
            if output_path:
                self.add_output(input_file, output_path)
            else:
                self.add_variable(input_file, input_file)
        else:
            raise Exception('Could not create single input %s, as input '
                            'already defined' % input_file)

    def add_gathering_input(self, input_file, common_path, starting_index,
                            number_of_files, output_path=None):
        if len(self.trigger_paths) == 0:
            star_count = common_path.count('*')
            if star_count == 0:
                # NOTE, Not really an exception case, since it is just
                # regular control flow. Consider using 'asserts' when validating
                # user API inputs
                raise Exception("common_path must contain a '*' character.")
            if star_count > 1:
                raise Exception("common_path should only contain one '*' character.")
            self.input_file = input_file
            if output_path:
                self.add_output(input_file, output_path)
            else:
                self.add_variable(input_file, input_file)
            for index in range(0, number_of_files):
                path = common_path.replace('*', str(index + starting_index))
                self.trigger_paths.append(path)
        else:
            raise Exception('Could not create gathering input %s, as input '
                            'already defined' % input_file)

    def add_output(self, output_name, output_location):
        if output_name not in self.outputs.keys():
            self.outputs[output_name] = output_location
            self.add_variable(output_name, output_name)
        else:
            raise Exception('Could not create output %s as already defined'
                            % output_name)

    def return_notebook(self, output_location):
        self.add_output(DEFAULT_JOB_FILE_INPUT, output_location)

    def add_recipe(self, recipe):
        self.recipes.append(recipe)

    def add_variable(self, variable_name, variable_value):
        if variable_name not in self.variables.keys():
            self.variables[variable_name] = variable_value
        else:
            raise Exception('Could not create variable %s as it is already '
                            'defined' % variable_name)
