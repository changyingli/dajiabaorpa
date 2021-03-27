def set_value_by_id(driver, id_, value):
    driver.execute_script(f'document.querySelector("#{id_}").value="{value}"')

def set_value_by_name(driver, name, value):
    driver.execute_script(f'document.getElementsByName("{name}")[0].value="{value}"')