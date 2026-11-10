import pytest
from backend.recipe_schema import Recipe

def document(url):
    return {'name':'精选粥','ingredients':[{'name':'小米'}],
            'steps':[{'text':'煮熟','images':[url]}], 'images':[url]}

def test_bundled_editorial_picture_can_be_saved_with_a_recipe():
    url='/editorial/pumpkin-millet.png'
    recipe=Recipe.model_validate(document(url))
    assert recipe.images==[url]
    assert recipe.steps[0].images==[url]

@pytest.mark.parametrize('url',['/editorial/missing.png','/editorial/../secret.png','https://example.com/picture.png'])
def test_editorial_picture_must_be_a_known_bundled_asset(url):
    with pytest.raises(ValueError):
        Recipe.model_validate(document(url))
