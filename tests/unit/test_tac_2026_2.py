from tac import TACGenerator


def test_for_in_has_real_iteration_and_correct_continue_break(parse):
    text = TACGenerator().generate_text(parse('for(var x in [1,2]) { if(x == 1) continue; break; }'))
    lines = text.splitlines()
    assert '= iter ' in text and '= iter_has_next ' in text and '= iter_next ' in text
    entry = next(line[:-1] for line in lines if line.startswith('FOR_IN_') and line.endswith(':'))
    end = next(line[:-1] for line in lines if line.startswith('END_FOR_IN_') and line.endswith(':'))
    assert f'goto {entry}' in text and f'goto {end}' in text


def test_do_continue_jumps_to_condition(parse):
    text = TACGenerator().generate_text(parse('do { continue; } while(false);'))
    lines = text.splitlines()
    check = next(line[:-1] for line in lines if line.startswith('DO_CHECK_') and line.endswith(':'))
    assert f'goto {check}' in lines
    assert lines.index(f'goto {check}') < lines.index(f'{check}:') < next(i for i,s in enumerate(lines) if s.startswith('if false'))


def test_short_circuit_call_is_after_guard(parse):
    for operator, branch in [('&&','ifFalse'), ('||','if')]:
        text = TACGenerator().generate_text(parse(f'print(false {operator} side_effect());'))
        lines = text.splitlines()
        guard = next(i for i,line in enumerate(lines) if line.startswith(branch + ' false goto LOGIC_END'))
        call = next(i for i,line in enumerate(lines) if '= call side_effect' in line)
        label = next(i for i,line in enumerate(lines) if line.startswith('LOGIC_END_') and line.endswith(':'))
        assert guard < call < label


def test_nested_calls_evaluate_arguments_before_outer_params(parse):
    lines = TACGenerator().generate_text(parse('outer(1, inner(2));')).splitlines()
    inner = next(i for i,s in enumerate(lines) if '= call inner, 1' in s)
    outer = next(i for i,s in enumerate(lines) if '= call outer, 2' in s)
    assert lines[outer-2].startswith('param ') and lines[outer-1].startswith('param ')
    assert inner < outer - 2


def test_oop_metadata_receivers_constructor_args_and_store_addresses(parse):
    source = 'class A { var x = 1; func same(number x) { return x; } } class B extends A {} var b = new B(2); b.x = 3; b.same(4); var a = matrix(2,2,0); a[0][1] = 8;'
    text = TACGenerator().generate_text(parse(source))
    assert 'class B extends A' in text and 'field x:' in text and 'func A.same:' in text
    assert 'arg this' in text and '= new B, 1' in text and '= callmethod ' in text
    assert 'field_addr' in text and 'index_addr' in text and 'load_ref' in text and 'store ' in text


def test_par_has_distinct_tasks_and_barrier(parse):
    text = TACGenerator().generate_text(parse('par { print(1); print(2); }'))
    assert text.count('= spawn ') == 2 and text.count('task_return') == 2
    assert text.count('\njoin ') == 2 and 'PAR_JOIN_' in text


def test_generator_is_reusable_and_strings_are_escaped(parse):
    generator = TACGenerator()
    program = parse('print("line\\nquote\\\"");')
    first = generator.generate_text(program)
    assert generator.generate_text(program) == first
    assert first.splitlines() == ['print "line\\nquote\\\""']


def test_shadowed_names_and_temporary_collisions_are_distinct(parse):
    text = TACGenerator().generate_text(parse('var t0 = 7; seq { var x = 1; print(x); } seq { var x = 2; print(x); } print(t0 + 1);'))
    assert 'x@S1 = 1' in text and 'x@S2 = 2' in text
    assert 'print x@S1' in text and 'print x@S2' in text
    assert 't1 = t0 + 1' in text and 't0 = t0 + 1' not in text
