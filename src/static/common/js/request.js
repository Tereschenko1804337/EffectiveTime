function request({
    url,
    method="GET",
    body={},
    form_data=null,
}) {
    method = method.toUpperCase();

    let options = {
        method: method,
        headers: {
            'X-CSRFToken': document.querySelector('input[name=csrfmiddlewaretoken]').value,
        }
    }

    if (!form_data) {
        options.headers['Content-Type'] = 'application/json';
    }

    if (method === 'GET'){
        const param = new URLSearchParams(body).toString();
    }
    else {
        if (form_data) {
            options.body = form_data;
        }
        else {
            options.body = JSON.stringify(body);
        }
    }

    return fetch(url, options)
        .then(async (response) => {
            if (!response.ok) {
                let errorText = await response.text();
                throw {status: response.status, message: JSON.parse(errorText)}
            }
            try{
                if (response.status !== 204) {
                    const contentType = response.headers.get('content-type') || '';

                    if (contentType.includes('application/json')) {
                        return await response.json();
                    }


                    return await response.text();
                }
            } catch(e) {
                return response.text();
            }
        })
        .then(data => {
            return data;

        })
        .catch((error) => {
            console.error(error);
        });
}