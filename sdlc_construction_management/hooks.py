def post_init_hook(env):
    env['construction.project']._assign_default_stages()
