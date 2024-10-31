# simple-leaderboard-api
An API for implementing leaderboards into your games

## How to use it
You'll first want to visit http://geraldburke.com/simple-leaderboard to get your GameID.
A GameID is unique to your game and email. You can have multiple games under the same email,
but to get a new GameID you'll need a new Game to generate it.

Once you have the GameID, you'll generally make GET requests to the API in exchange for your leaderboard stats. 

## Actions
The base URL for the API is `https://geraldburke.com/apis/simple-leaderboard/`

To make a call, you must specify an action. There are three of these.

### newScore
This will look like `https://geraldburke.com/apis/simple-leaderboard/?action=newScore`

This is how you will add new scores to the leaderboard.

This endpoint take 3 paramaters. All three must have a value to make a successful call.

1) `gameID` - The unique number you receive when you sign up with your email
2) `score` - The numeric value of the user score. It's an integer, so be kind with your scale
3) `userName` - The name of the user that got the score

A complete request to add a new score should look something like this

`https://geraldburke.com/apis/simple-leaderboard/?action=newScore&gameID=1&score=1000&userName=geraldfingburke`

Verbose, isn't it? I promised a simple api, not a short one.

### topScores
This will look like `https://geraldburke.com/apis/simple-leaderboard/?action=topScores`

This is how you will read values from the leaderboard.

This endpoint has two paramaters (and one of them is optional!)

1) `gameID` - The unique number you receive when you sign up with your email
2) `count` - The number of scores to pull. If you leave this off, you'll just get ten. If there are fewer records than the count, you'll get what you have.

A complete request to get top scores should look like this

`https://geraldburke.com/apis/simple-leaderboard/?action=topScores&gameID=1&count=10`

Remember, you can leave off the count. As a matter of fact, since the default is 10, there is virtually no difference between that call and a call without the count parameter.

### userScores
This will look like `https://geraldburke.com/apis/simple-leaderboard/?action=userScores`

This one lets you get scores by the name of the user that scored them.

This endpoint brings us back to three parameters (still one optional!)

1)`gameID` - The unique number you receive when you sign up with your email
2)`userName` - The name of the user you want to get scores for
3)`count` - The number of scores to pull. If you leave this off, you'll just get ten. If there are fewer records than the count, you'll get what you have.

`https://geraldburke.com/apis/simple-leaderboard/?action=topScores&gameID=1&userName=geraldfingburke&count=10`

Remember, you can leave off the count. As a matter of fact, since the default is 10, there is virtually no difference between that call and a call without the count parameter.

## Attribution and License Info

I don't actually know what the license is, I just picked one that sounded permissive. That is the spirit of this endeavor. Feel free to use this however you would like. 

I don't need myself or the project to be credited if you do use this, but I absolutely love to hear when people use my work, so if you want to shoot me a message with a link to your thing, I would love to check it out.
