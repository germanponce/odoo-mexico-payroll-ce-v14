update hr_salary_rule
set amount_python_compute=replace(amount_python_compute, 'datetime.strptime(', '');

update hr_salary_rule
set amount_python_compute=replace(amount_python_compute, ', ''%Y-%m-%d %H:%M:%S'')', '');

update hr_salary_rule
set amount_python_compute=replace(amount_python_compute, ', ''%Y-%m-%d'')', '');

update hr_salary_rule
set amount_python_compute=replace(amount_python_compute, ',''%Y-%m-%d'')', '');


