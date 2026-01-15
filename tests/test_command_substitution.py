# Copyright 2024, Peter Birch, mailto:peter@lightlogic.co.uk
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from gator.common.utility import find_command_substitutions


class TestFindCommandSubstitutions:
    """Test suite for finding command substitutions in text"""

    def test_find_simple_command_substitution(self):
        """Test finding simple $(cmd) patterns"""
        text = "echo $(hostname)"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0] == (5, 16, "$(hostname)")

    def test_find_nested_command_substitution(self):
        """Test finding nested $(cmd $(cmd)) patterns"""
        text = "echo $(echo $(whoami))"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0] == (5, 22, "$(echo $(whoami))")

    def test_find_complex_nested_command_substitution(self):
        """Test finding complex nested patterns like $(date +%Y-$(date +%m))"""
        text = "echo $(date +%Y-$(date +%m))"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0] == (5, 28, "$(date +%Y-$(date +%m))")

    def test_find_backticks(self):
        """Test finding `cmd` backtick patterns"""
        text = "echo `hostname`"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0] == (5, 15, "`hostname`")

    def test_find_escaped_backticks(self):
        """Test handling escaped backticks"""
        text = r"echo `echo \`nested\``"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        # Should capture the whole thing including escaped backticks
        assert subs[0][2] == r"`echo \`nested\``"

    def test_find_multiple_substitutions(self):
        """Test finding multiple command substitutions in one string"""
        text = "echo $(cmd) and `another`"
        subs = find_command_substitutions(text)
        assert len(subs) == 2
        assert subs[0] == (5, 11, "$(cmd)")
        assert subs[1] == (16, 25, "`another`")

    def test_find_with_variables(self):
        """Test that variables don't interfere with finding command substitutions"""
        text = "echo $HOME and $(hostname)"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0] == (15, 26, "$(hostname)")

    def test_find_unmatched_paren(self):
        """Test that unmatched parentheses are handled gracefully"""
        text = "echo $(incomplete"
        subs = find_command_substitutions(text)
        # Should not find anything or handle gracefully
        assert len(subs) == 0

    def test_multiple_nested_levels(self):
        """Test deeply nested command substitutions"""
        text = "echo $(outer $(middle $(inner)))"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(outer $(middle $(inner)))"

    def test_parentheses_in_double_quotes(self):
        """Test that parentheses inside double quotes are handled correctly"""
        text = '$(echo ")")'
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0] == (0, 11, '$(echo ")")')

    def test_parentheses_in_single_quotes(self):
        """Test that parentheses inside single quotes are handled correctly"""
        text = "$(echo ')')"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0] == (0, 11, "$(echo ')')")

    def test_escaped_parentheses(self):
        """Test that escaped parentheses are handled correctly"""
        text = r"$(echo \))"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0] == (0, 10, r"$(echo \))")

    def test_complex_quoting(self):
        """Test complex quoting scenarios"""
        text = """$(echo "foo (bar)" 'baz (qux)' end)"""
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == """$(echo "foo (bar)" 'baz (qux)' end)"""

    def test_nested_quotes(self):
        """Test nested command substitution with quotes"""
        text = '$(echo "outer $(echo inner)")'
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == '$(echo "outer $(echo inner)")'

    def test_mixed_quotes_in_nested(self):
        """Test nested command substitution with mixed quotes"""
        text = """$(echo "$(echo 'nested')")"""
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == """$(echo "$(echo 'nested')")"""

    def test_backslash_in_double_quotes(self):
        """Test backslash escaping inside double quotes"""
        text = r'$(echo "foo \" bar")'
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == r'$(echo "foo \" bar")'

    def test_backslash_in_single_quotes(self):
        """Test that backslashes are literal in single quotes"""
        # Backslashes are literal in single quotes, so this is valid:
        text = r"$(echo 'foo \ bar')"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == r"$(echo 'foo \ bar')"

    def test_dollar_in_single_quotes(self):
        """Test that $ is literal in single quotes"""
        text = "$(echo '$HOME')"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(echo '$HOME')"

    def test_dollar_in_double_quotes(self):
        """Test that $ is special in double quotes"""
        text = '$(echo "$HOME")'
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == '$(echo "$HOME")'

    def test_multiple_levels_with_quotes(self):
        """Test deeply nested substitutions with quotes"""
        text = "$(outer \"$(middle '$(inner)')\")"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(outer \"$(middle '$(inner)')\")"

    def test_backticks_with_quotes(self):
        """Test backticks with quoted content"""
        text = '`echo "hello (world)"`'
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == '`echo "hello (world)"`'

    def test_backticks_with_nested_backticks_escaped(self):
        """Test escaped backticks inside backtick command substitution"""
        text = r"`echo \`nested\``"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == r"`echo \`nested\``"

    def test_empty_quotes(self):
        """Test empty quoted strings"""
        text = "$(echo \"\" '')"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(echo \"\" '')"

    def test_adjacent_quotes(self):
        """Test adjacent quoted strings"""
        text = "$(echo \"foo\"'bar')"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(echo \"foo\"'bar')"

    def test_escaped_dollar_outside_quotes(self):
        """Test that escaped dollars are preserved"""
        text = r"$(echo \$HOME)"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == r"$(echo \$HOME)"

    def test_multiple_commands_with_quotes(self):
        """Test multiple command substitutions with various quoting"""
        text = """$(echo "foo)") and $(echo ')') and `echo ")"`"""
        subs = find_command_substitutions(text)
        assert len(subs) == 3
        assert subs[0][2] == '$(echo "foo)")'
        assert subs[1][2] == "$(echo ')')"
        assert subs[2][2] == '`echo ")"`'

    def test_ansi_c_quoting(self):
        """Test ANSI-C quoting $'...' with escape sequences"""
        text = r"$(echo $'hello\nworld')"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == r"$(echo $'hello\nworld')"

    def test_arithmetic_expansion(self):
        """Test arithmetic expansion $((...)) which has double parens"""
        text = "$(echo $((1 + 2)))"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(echo $((1 + 2)))"

    def test_arithmetic_with_nested_parens(self):
        """Test arithmetic with nested expressions"""
        text = "$(echo $(($(echo 5) + 3)))"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(echo $(($(echo 5) + 3)))"

    def test_parameter_expansion(self):
        """Test various parameter expansion forms"""
        text = "$(echo ${var:-default})"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(echo ${var:-default})"

    def test_parameter_expansion_with_parens(self):
        """Test parameter expansion with parentheses in default"""
        text = '$(echo ${var:-"default (value)"})'
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == '$(echo ${var:-"default (value)"})'

    def test_command_with_semicolons(self):
        """Test commands with semicolons"""
        text = "$(echo foo; echo bar)"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(echo foo; echo bar)"

    def test_command_with_pipes(self):
        """Test commands with pipes"""
        text = "$(echo foo | grep f)"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(echo foo | grep f)"

    def test_command_with_redirects(self):
        """Test commands with redirections"""
        text = "$(cat < file.txt > output.txt)"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(cat < file.txt > output.txt)"

    def test_glob_patterns(self):
        """Test glob patterns inside command substitution"""
        text = "$(ls *.txt)"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(ls *.txt)"

    def test_brace_expansion(self):
        """Test brace expansion"""
        text = "$(echo {a,b,c})"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(echo {a,b,c})"

    def test_tilde_expansion(self):
        """Test tilde expansion"""
        text = "$(ls ~/Documents)"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(ls ~/Documents)"

    def test_no_command_substitutions(self):
        """Test text with no command substitutions"""
        text = "echo hello world"
        subs = find_command_substitutions(text)
        assert len(subs) == 0

    def test_empty_string(self):
        """Test empty string"""
        subs = find_command_substitutions("")
        assert len(subs) == 0
