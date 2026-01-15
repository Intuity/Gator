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

from gator.common.utility import expand_vars_preserve_commands, find_command_substitutions


class TestCommandSubstitution:
    """Test suite for command substitution handling in variable expansion"""

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

    def test_expand_preserve_simple_command_substitution(self):
        """Test that simple command substitutions are preserved"""
        text = "echo Hello from $(hostname)"
        result = expand_vars_preserve_commands(text, {})
        assert result == "echo Hello from $(hostname)"

    def test_expand_preserve_nested_command_substitution(self):
        """Test that nested command substitutions are preserved"""
        text = "echo $(echo $(whoami))"
        result = expand_vars_preserve_commands(text, {})
        assert result == "echo $(echo $(whoami))"

    def test_expand_preserve_complex_nested(self):
        """Test that complex nested patterns are preserved"""
        text = "echo $(date +%Y-$(date +%m))"
        result = expand_vars_preserve_commands(text, {})
        assert result == "echo $(date +%Y-$(date +%m))"

    def test_expand_preserve_backticks(self):
        """Test that backticks are preserved"""
        text = "echo `hostname`"
        result = expand_vars_preserve_commands(text, {})
        assert result == "echo `hostname`"

    def test_expand_variables_without_commands(self):
        """Test that variables are expanded when no command substitutions present"""
        text = "echo $HOME"
        result = expand_vars_preserve_commands(text, {"HOME": "/root"})
        assert result == "echo /root"

    def test_expand_braced_variables(self):
        """Test that braced variables are expanded"""
        text = "echo ${HOME}"
        result = expand_vars_preserve_commands(text, {"HOME": "/root"})
        assert result == "echo /root"

    def test_expand_variables_with_commands(self):
        """Test that variables are expanded but commands are preserved"""
        text = "echo $HOME and $(hostname)"
        result = expand_vars_preserve_commands(text, {"HOME": "/root"})
        assert result == "echo /root and $(hostname)"

    def test_expand_default_values(self):
        """Test expandvars default value syntax ${VAR:-default}"""
        text = "echo ${HOME:-/default}"
        result = expand_vars_preserve_commands(text, {})
        assert result == "echo /default"

    def test_expand_braced_with_suffix(self):
        """Test braced variables with suffixes"""
        text = "echo ${HOME}/subdir"
        result = expand_vars_preserve_commands(text, {"HOME": "/root"})
        assert result == "echo /root/subdir"

    def test_expand_multiple_variables(self):
        """Test multiple variable expansions"""
        text = "echo $HOME$USER"
        result = expand_vars_preserve_commands(text, {"HOME": "/root", "USER": "alice"})
        assert result == "echo /rootalice"

    def test_expand_complex_mixed(self):
        """Test complex mix of variables and command substitutions"""
        text = "echo $(date +%Y) in $HOME"
        result = expand_vars_preserve_commands(text, {"HOME": "/root"})
        assert result == "echo $(date +%Y) in /root"

    def test_expand_backticks_with_variables(self):
        """Test backticks preserved with variable expansion"""
        text = "echo `cat /etc/hostname` and $USER"
        result = expand_vars_preserve_commands(text, {"USER": "bob"})
        assert result == "echo `cat /etc/hostname` and bob"

    def test_empty_string(self):
        """Test that empty strings are handled"""
        result = expand_vars_preserve_commands("", {})
        assert result == ""

    def test_no_variables_no_commands(self):
        """Test plain text with no variables or commands"""
        text = "echo hello world"
        result = expand_vars_preserve_commands(text, {})
        assert result == "echo hello world"

    def test_multiple_nested_levels(self):
        """Test deeply nested command substitutions"""
        text = "echo $(outer $(middle $(inner)))"
        subs = find_command_substitutions(text)
        assert len(subs) == 1
        assert subs[0][2] == "$(outer $(middle $(inner)))"

        result = expand_vars_preserve_commands(text, {})
        assert result == "echo $(outer $(middle $(inner)))"

    def test_command_with_special_chars(self):
        """Test command substitution with special characters"""
        text = "echo $(grep -E '^pattern' file.txt)"
        result = expand_vars_preserve_commands(text, {})
        assert result == "echo $(grep -E '^pattern' file.txt)"

    def test_placeholder_collision_resistance(self):
        """Test that placeholder names don't collide with actual text"""
        text = "echo __GATOR_CMD_SUB_0__ $(hostname)"
        result = expand_vars_preserve_commands(text, {})
        # Should preserve both the literal text and the command substitution
        assert "$(hostname)" in result
        assert "__GATOR_CMD_SUB_0__" in result
