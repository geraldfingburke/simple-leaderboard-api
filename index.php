<?php
header("Access-Control-Allow-Headers: Authorization, Content-Type");
header("Access-Control-Allow-Origin: *");
header('content-type: application/json; charset=utf-8');

function get_pdo() {
  require "dbConfig.php";
  
  $dsn = "mysql:dbname=".DB_NAME.";host=".DB_HOST;
  $user = DB_USER;
  $pass = DB_PASS;
  
  return new PDO($dsn, $user, $pass);
}

function record_new_user($email, $gameName) {
  $dbh = get_pdo();
  
  //Checks for an existing gameID
  $stmt = $dbh->prepare("SELECT gameID FROM Users WHERE email = :email_value AND gameName = :gameName_value");
  $stmt->bindValue(":email_value", $email, PDO::PARAM_STR);
  $stmt->bindValue(":gameName_value", $gameName, PDO::PARAM_STR);
  $stmt->execute();
  
  $results = $stmt->fetchAll();
  
  if(count($results) > 0) {
    echo json_encode($results[0]["gameID"]);
    die();
  }
  
  $stmt = $dbh->prepare("INSERT INTO Users (email, gameName) VALUES(:email_value, :gameName_value)");
  $stmt->bindValue(":email_value", $email, PDO::PARAM_STR);
  $stmt->bindValue(":gameName_value", $gameName, PDO::PARAM_STR);
  $stmt->execute();
  
  echo json_encode($dbh->lastInsertId());
  die();
}

function record_new_score($gameID, $score, $userName) {
  $dbh = get_pdo();
  
  //Prevents users from adding scores for a gameID that doesn't 'exist'
  $stmt = $dbh->prepare("SELECT gameID FROM Users WHERE gameID = :gameID_value");
  $stmt->bindValue(":gameID_value", $gameID, PDO::PARAM_INT);
  $stmt->execute();
  
  $results = $stmt->fetchAll();
  
  if(count($results) == 0) {
    echo("Invalid GameID");
    die();
  }
  
  $stmt = $dbh->prepare("INSERT INTO Scores (gameID, score, userName) VALUES(:gameID_value, :score_value, :userName_value)");
  $stmt->bindValue(":gameID_value", $gameID, PDO::PARAM_INT);
  $stmt->bindValue(":score_value", $score, PDO::PARAM_INT);
  $stmt->bindValue(":userName_value", $userName, PDO::PARAM_STR);
  $stmt->execute();
}

function get_top_scores($gameID, $count) {
  $dbh = get_pdo();
  $stmt = $dbh->prepare("SELECT score, userName FROM Scores WHERE gameID = :gameID_value ORDER BY score DESC LIMIT :count_value");
  $stmt->bindValue(":gameID_value", $gameID, PDO::PARAM_INT);
  $stmt->bindValue(":count_value", $count, PDO::PARAM_INT);
  $stmt->execute();
  
  $results = $stmt->fetchAll();
  
  $json = Array();
  
  foreach($results as $result) {
    array_push($json, ["userName" => $result["userName"], "score" => $result["score"]]);
  }
  
  return json_encode($json);
}

function get_user_scores($gameID, $userName, $count) {
  $dbh = get_pdo();
  $stmt = $dbh->prepare("SELECT score, userName FROM Scores WHERE gameID = :gameID_value AND userName = :userName_value ORDER BY score DESC LIMIT :count_value");
  $stmt->bindValue(":gameID_value", $gameID, PDO::PARAM_INT);
  $stmt->bindValue(":userName_value", $userName, PDO::PARAM_STR);
  $stmt->bindValue(":count_value", $count, PDO::PARAM_INT);
  $stmt->execute();
  
  $results = $stmt->fetchAll();
  
  $json = array();
  
  foreach($results as $result) {
    array_push($json, [$result["userName"] => $result["score"]]);
  }
  
  return json_encode($json);
}


if ($_GET["action"] == "newScore") {
  if ($_GET["gameID"] && $_GET["score"] && $_GET["userName"]) {
    record_new_score($_GET["gameID"], $_GET["score"], $_GET["userName"]);
    echo "Success";
    die();
  }
  echo "Invalid Params";
  die();
}



if ($_GET["action"] == "topScores") {
  if ($_GET["count"] && $_GET["gameID"]) {
    $json = get_top_scores($_GET["gameID"], $_GET["count"]);
    echo $json;
    die();
  } else if ($_GET["gameID"]) {
    $json = get_top_scores($_GET["gameID"], 10);
    echo $json;
    die();
  }
  echo "Invalid params";
  die();
}



if ($_GET["action"] == "userScores") {
  if (!$_GET["userName"] || !$_GET["gameID"]) {
    echo "Invalid params";
    die();
  }
  else if ($_GET["count"]) {
    $json = get_user_scores($_GET["gameID"], $_GET["userName"], $_GET["count"]);
    echo $json;
    die();
  }
  $json = get_user_scores($_GET["gameID"], $_GET["userName"], 10);
  echo $json;
  die();
}



$json = file_get_contents('php://input');

$data = json_decode($json, true);

if ($data["action"] == "addUser") {
  if (!$data["email"] || !$data["gameName"]) {
    echo "Invalid params";
    die();
  }
  record_new_user($data["email"], $data["gameName"]);
  echo "Success";

}
?>
