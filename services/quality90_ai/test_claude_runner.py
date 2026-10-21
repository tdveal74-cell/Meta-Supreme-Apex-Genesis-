import unittest
import claude_runner as r

class RunnerTests(unittest.TestCase):
    def test_process_environment_does_not_inherit_paid_routes_or_agent_tools(self):
        e=r.clean_env({'HOME':'/root','ANTHROPIC_API_KEY':'not-real','ANTHROPIC_AUTH_TOKEN':'not-real','ANTHROPIC_BASE_URL':'https://wrong','CLAUDE_CODE_OAUTH_TOKEN':'not-real','HTTPS_PROXY':'https://wrong','CLAUDE_CODE_USE_BEDROCK':'1'})
        for k in ['ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','CLAUDE_CODE_OAUTH_TOKEN','HTTPS_PROXY','CLAUDE_CODE_USE_BEDROCK']:
            self.assertNotIn(k,e)
        self.assertEqual(e['CLAUDE_CODE_DISABLE_FAST_MODE'],'1')
    def test_model_run_disables_context_tools_hooks_session_reuse(self):
        a=r.review_args('/root/.local/bin/claude')
        for flag in ['--safe-mode','--restricted','--no-session-persistence','--strict-mcp-config','--json-schema','--tools']:
            self.assertIn(flag,a)
        self.assertEqual(a[a.index('--tools')+1],'')
        self.assertEqual(a[a.index('--model')+1],'sonnet')
        self.assertNotIn('--dangerously-skip-permissions',a)
        self.assertNotIn('--resume',a)
    def test_observation_is_taken_from_actual_runtime_not_report_text(self):
        out={'is_error':False,'session_id':'run-abc','modelUsage':{'claude-sonnet-5':{}},'structured_output':{'score':99,'reviewer':'human'}}
        obs=r.runtime_observation(out)
        self.assertEqual(obs['provider'],'anthropic')
        self.assertEqual(obs['model'],'claude-sonnet-5')
        self.assertEqual(obs['source'],'observed_cli_run')
        with self.assertRaises(ValueError):r.runtime_observation({'is_error':True})
        with self.assertRaises(ValueError):r.runtime_observation({'session_id':'x','modelUsage':{'wrong':{}}})

if __name__=='__main__':unittest.main()
